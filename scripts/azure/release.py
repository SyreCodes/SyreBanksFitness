"""Release an immutable image to existing Azure resources; never provision or downgrade DBs."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class ReleaseError(RuntimeError):
    pass


def single_container(resource):
    containers = resource["properties"]["template"]["containers"]
    if len(containers) != 1:
        raise ReleaseError("Release expects exactly one container per app/job")
    return containers[0]


class Release:
    def __init__(self, subscription, group, api, worker, migrate, scheduler, image, release_id):
        if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
            raise ReleaseError("IMAGE must be an immutable repository@sha256:digest")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,45}[a-z0-9]", release_id) or "--" in release_id:
            raise ReleaseError("Invalid release revision suffix")
        self.subscription, self.group = subscription, group
        self.api, self.worker, self.migrate, self.scheduler = api, worker, migrate, scheduler
        if len({api, worker, migrate, scheduler}) != 4:
            raise ReleaseError("API, worker, migration and scheduler names must be distinct")
        self.image, self.release_id = image, release_id
        self.poll_seconds = 10
        self.attempts = 90

    def az(self, *args):
        result = subprocess.run(
            ["az", *args, "--subscription", self.subscription, "--resource-group", self.group,
             "--only-show-errors", "--output", "json"],
            capture_output=True, text=True, timeout=300, check=False,
        )
        if result.returncode:
            # Azure errors can contain environment/secret values. Keep raw output off CI logs.
            raise ReleaseError(f"Azure command failed: {' '.join(args[:3])}; inspect Azure activity logs")
        return json.loads(result.stdout or "null")

    def show(self, name, job=False):
        return self.az("containerapp", *(["job"] if job else []), "show", "--name", name)

    def poll(self, check, description):
        for attempt in range(self.attempts):
            result = check()
            if result:
                return result
            if attempt + 1 < self.attempts:
                time.sleep(self.poll_seconds)
        raise ReleaseError(f"Timed out waiting for {description}")

    def revision_ready(self, name, revision, expected_image):
        def check():
            state = self.az("containerapp", "revision", "show", "--name", name,
                            "--revision", revision)
            props = state["properties"]
            if props.get("provisioningState") in {"Failed", "Deprovisioned"} or props.get("runningState") in {"Failed", "Degraded"}:
                raise ReleaseError(f"Revision {revision} failed to become healthy")
            if (props.get("provisioningState") == "Provisioned"
                    and props.get("healthState") == "Healthy"
                    and props.get("runningState") in {"Running", "RunningAtMaxScale"}
                    and props.get("active") is True
                    and single_container(state)["image"] == expected_image):
                return props
            return None
        return self.poll(check, f"healthy revision {revision}")

    def smoke(self, host):
        if not re.fullmatch(r"[a-zA-Z0-9.-]+", host or ""):
            raise ReleaseError("Azure did not return a valid HTTPS host")

        def check():
            try:
                with urllib.request.urlopen(f"https://{host}/ready", timeout=20) as response:
                    ready = json.load(response)
                with urllib.request.urlopen(f"https://{host}/login", timeout=20) as response:
                    login = response.read(2_000_000)
                return ready.get("status") == "ready" and b'id="root"' in login
            except (OSError, ValueError, urllib.error.URLError):
                return False
        self.poll(check, f"readiness and login page at {host}")

    def run_job(self, name, container):
        execution = self.az("containerapp", "job", "start", "--name", name,
                            "--container-name", container, "--image", self.image)
        execution_name = execution.get("name")
        if not execution_name:
            raise ReleaseError(f"No execution identity returned for {name}; inspect job before retrying")
        print(f"Waiting for {name} execution {execution_name}", flush=True)

        def check():
            state = self.az("containerapp", "job", "execution", "show", "--name", name,
                            "--job-execution-name", execution_name)
            if state.get("name") != execution_name:
                raise ReleaseError("Azure returned a different job execution")
            status = state["properties"].get("status")
            if status in {"Failed", "Stopped", "Degraded"}:
                raise ReleaseError(f"Job {name} execution {execution_name}: {status}")
            return status == "Succeeded"
        try:
            self.poll(check, f"job execution {execution_name}")
        except Exception:
            try:
                self.az("containerapp", "job", "stop", "--name", name,
                        "--job-execution-name", execution_name)
            except (ReleaseError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                print(f"WARNING: could not confirm stop of {execution_name}; inspect before retrying", file=sys.stderr)
            raise

    def traffic(self, revision):
        self.az("containerapp", "ingress", "traffic", "set", "--name", self.api,
                "--revision-weight", f"{revision}=100")

    def update_app(self, name, container, image, suffix):
        self.az("containerapp", "update", "--name", name, "--container-name", container,
                "--image", image, "--revision-suffix", suffix)
        return self.revision_ready(name, f"{name}--{suffix}", image)

    def update_scheduler(self, container, image):
        self.az("containerapp", "job", "update", "--name", self.scheduler,
                "--container-name", container, "--image", image)
        state = self.show(self.scheduler, job=True)
        if (state["properties"].get("provisioningState") != "Succeeded"
                or single_container(state)["image"] != image):
            raise ReleaseError("Scheduler update could not be verified")

    def run(self):
        # Read every required resource before any mutation or migration.
        api, worker = self.show(self.api), self.show(self.worker)
        migrate, scheduler = self.show(self.migrate, job=True), self.show(self.scheduler, job=True)
        containers = [single_container(resource) for resource in (api, worker, migrate, scheduler)]
        api_container, worker_container, migrate_container, scheduler_container = containers
        properties = api["properties"]
        ingress = properties["configuration"].get("ingress") or {}
        public_url = next((entry.get("value") for entry in api_container.get("env", [])
                           if entry["name"] == "PUBLIC_WEB_URL"), None)
        public_host = ingress.get("fqdn")
        if public_url is not None:
            endpoint = urllib.parse.urlsplit(public_url)
            if (endpoint.scheme != "https" or not endpoint.hostname
                    or endpoint.username or endpoint.password or endpoint.port
                    or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment):
                raise ReleaseError("PUBLIC_WEB_URL must be an HTTPS origin without credentials, port or path")
            public_host = endpoint.hostname
        weighted = [entry for entry in ingress.get("traffic", []) if entry.get("weight", 0) > 0]
        if len(weighted) != 1 or weighted[0]["weight"] != 100 or not ingress.get("external"):
            raise ReleaseError("API must have external HTTPS ingress and one revision receiving 100% traffic")
        old_revision = (properties.get("latestReadyRevisionName") if weighted[0].get("latestRevision")
                        else weighted[0].get("revisionName"))
        if not old_revision:
            raise ReleaseError("Cannot identify previous API revision")
        if worker["properties"]["configuration"].get("activeRevisionsMode") != "Single":
            raise ReleaseError("Worker must use single revision mode")
        if worker["properties"]["template"].get("scale", {}).get("minReplicas", 0) < 1:
            raise ReleaseError("Worker must keep at least one replica running")
        if migrate["properties"]["configuration"].get("triggerType") != "Manual":
            raise ReleaseError("Migration job must be manually triggered")
        if scheduler["properties"]["configuration"].get("triggerType") != "Schedule":
            raise ReleaseError("Outbox job must have a schedule")
        for job in (migrate, scheduler):
            config = job["properties"]["configuration"]
            trigger = config.get("manualTriggerConfig", config.get("scheduleTriggerConfig", {}))
            if trigger.get("parallelism") != 1 or trigger.get("replicaCompletionCount") != 1:
                raise ReleaseError("Jobs must run one replica per execution")
        for resource, expected in ((migrate, ["alembic", "upgrade", "head"]),
                                   (scheduler, ["python", "-m", "app.dispatch_outbox"])):
            container = single_container(resource)
            if container.get("command", []) + (container.get("args") or []) != expected:
                raise ReleaseError("Job command does not match its migration or outbox purpose")
        executions = self.az("containerapp", "job", "execution", "list", "--name", self.migrate)
        if any(item["properties"].get("status") in {"Running", "Processing", "Pending"} for item in executions):
            raise ReleaseError("A migration execution is already active; inspect it before retrying")

        print("Preflight passed; running backward-compatible database migrations", flush=True)
        self.run_job(self.migrate, migrate_container["name"])
        candidate = f"{self.api}--{self.release_id}"
        candidate_started = worker_changed = scheduler_changed = False
        try:
            self.az("containerapp", "revision", "set-mode", "--name", self.api, "--mode", "multiple")
            # Never leave a latestRevision=100 rule in place when staging a new revision.
            self.traffic(old_revision)
            candidate_started = True
            revision = self.update_app(self.api, api_container["name"], self.image, self.release_id)
            self.smoke(revision.get("fqdn"))
            worker_changed = True
            self.update_app(self.worker, worker_container["name"], self.image, self.release_id)
            scheduler_changed = True
            self.update_scheduler(scheduler_container["name"], self.image)
            self.run_job(self.scheduler, scheduler_container["name"])
            self.traffic(candidate)
            self.smoke(ingress.get("fqdn"))
            if public_host != ingress.get("fqdn"):
                self.smoke(public_host)
        except Exception:
            print("Release failed; restoring previous traffic and background images. Database stays upgraded.", file=sys.stderr)
            repairs = [("API traffic", lambda: self.traffic(old_revision))]
            if scheduler_changed:
                repairs.append(("scheduler", lambda: self.update_scheduler(scheduler_container["name"], scheduler_container["image"])))
            if worker_changed:
                repairs.append(("worker", lambda: self.update_app(self.worker, worker_container["name"], worker_container["image"], self.release_id + "-rb")))
            if candidate_started:
                repairs.append(("candidate", lambda: self.az("containerapp", "revision", "deactivate", "--name", self.api, "--revision", candidate)))
            traffic_restored = False
            for name, repair in repairs:
                if name == "candidate" and not traffic_restored:
                    print("WARNING: leaving candidate active because traffic restoration was not confirmed", file=sys.stderr)
                    continue
                try:
                    repair()
                    if name == "API traffic":
                        traffic_restored = True
                except (ReleaseError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                    print(f"WARNING: {name} rollback needs operator attention", file=sys.stderr)
            raise
        # Keep the old revision for rollback without paying for idle replicas.
        try:
            self.az("containerapp", "revision", "deactivate", "--name", self.api, "--revision", old_revision)
        except (ReleaseError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            print("WARNING: release healthy, but previous API revision remains active", file=sys.stderr)
        print(f"Released {self.image} to https://{public_host}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    names = ("AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_API_APP", "AZURE_WORKER_APP",
             "AZURE_MIGRATION_JOB", "AZURE_SCHEDULER_JOB")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        parser.error("Missing environment variables: " + ", ".join(missing))
    try:
        Release(*(os.environ[name] for name in names), args.image, args.release_id).run()
    except (ReleaseError, KeyError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
