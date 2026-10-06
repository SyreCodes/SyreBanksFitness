import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
export class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state = {failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  componentDidCatch(error:Error,info:ErrorInfo){console.error('Workspace rendering failed',error.message,info.componentStack);}
  render(){if(this.state.failed)return <main className="foundation"><div className="brand-mark">S</div><h1 style={{fontSize:'2rem'}}>Let’s get you back on track.</h1><p className="muted">This screen couldn’t load. Refresh the workspace to try again.</p><button className="button button-primary" style={{marginTop:20}} onClick={()=>window.location.reload()}>Refresh workspace</button></main>;return this.props.children;}
}
