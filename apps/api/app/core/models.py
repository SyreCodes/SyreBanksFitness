"""Model registry used by Alembic; domain modules own their tables."""
from app.modules.admin.models import AuditLog
from app.modules.auth.models import ActionToken, RefreshSession, User
from app.modules.clients.models import ClientProfile, Consent
from app.modules.cms.models import BlogPost, MediaAsset, Setting
from app.modules.coaching.models import Exercise, Measurement, Program, ProgramAssignment, WorkoutSession
from app.modules.commerce.models import Invoice, Order, Payment, Product, Subscription
from app.modules.experience.models import Checkin, Habit, HabitLog, Message, Notification
from app.modules.leads.models import Lead
from app.modules.scheduling.models import Booking

__all__ = ["ActionToken", "AuditLog", "BlogPost", "Booking", "Checkin", "ClientProfile", "Consent", "Exercise", "Habit", "HabitLog", "Invoice", "Lead", "Measurement", "MediaAsset", "Message", "Notification", "Order", "Payment", "Product", "Program", "ProgramAssignment", "RefreshSession", "Setting", "Subscription", "User", "WorkoutSession"]
