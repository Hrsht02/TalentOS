import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ArrowRight, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CheckCircle2, ChevronDown, CircleHelp, Command, FileText, GraduationCap, LayoutDashboard, LogOut, Search, ShieldCheck, Sparkles, Users, Zap } from "lucide-react";
import { apiRequest, clearSession, saveSession } from "./api";

const initialUser = () => {
  try { return JSON.parse(localStorage.getItem("talentos_user") || "null"); } catch { return null; }
};

function AuthPanel({ mode, onSuccess, onMode }) {
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "STUDENT", organization_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";
  const change = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  async function submit(event) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const path = isRegister ? "/auth/register" : "/auth/login";
      const body = isRegister ? form : { email: form.email, password: form.password };
      const data = await apiRequest(path, { method: "POST", body: JSON.stringify(body) });
      saveSession(data); onSuccess(data.user);
    } catch (err) { setError(err.message || "Something went wrong"); }
    finally { setBusy(false); }
  }
  return <div className="auth-card">
    <div className="auth-brand"><span className="brand-mark"><Command size={19}/></span><span>TalentOS</span></div>
    <p className="eyebrow">{isRegister ? "CREATE YOUR WORKSPACE" : "WELCOME BACK"}</p>
    <h1>{isRegister ? "Build your next opportunity." : "Your hiring workspace."}</h1>
    <p className="muted">{isRegister ? "One profile. Better matches. A clearer path forward." : "Sign in to continue your recruitment workflow."}</p>
    <form onSubmit={submit} className="auth-form">
      {isRegister && <label>Full name<input required minLength="2" value={form.full_name} onChange={(e)=>change("full_name",e.target.value)} placeholder="Your full name"/></label>}
      <label>Email address<input required type="email" value={form.email} onChange={(e)=>change("email",e.target.value)} placeholder="you@example.com"/></label>
      <label>Password<input required minLength={isRegister ? 12 : 1} type="password" value={form.password} onChange={(e)=>change("password",e.target.value)} placeholder={isRegister ? "At least 12 characters" : "Your password"}/></label>
      {isRegister && <><label>I'm joining as<select value={form.role} onChange={(e)=>change("role",e.target.value)}><option value="STUDENT">Student / Candidate</option><option value="COMPANY_HR">Company / Employer</option><option value="AGENCY_MEMBER">Recruitment agency</option></select></label>
      {form.role !== "STUDENT" && <label>Organization name<input required value={form.organization_name} onChange={(e)=>change("organization_name",e.target.value)} placeholder="Company or agency name"/></label>}</>}
      {error && <div className="error-message">{error}</div>}
      <button className="primary-button full-button" disabled={busy}>{busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"} <ArrowRight size={16}/></button>
    </form>
    <p className="auth-switch">{isRegister ? "Already have an account?" : "New to TalentOS?"} <button onClick={()=>onMode(isRegister ? "login" : "register")}>{isRegister ? "Sign in" : "Create account"}</button></p>
    <p className="fine-print">By continuing, you agree to use TalentOS responsibly. AI recommendations support decisions; they don't replace human judgment.</p>
  </div>;
}

function Dashboard({ user, onLogout }) {
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState("");
  useEffect(() => {
    if (user?.role === "ADMIN") apiRequest("/admin/overview").then(setStats).catch((e)=>setStatus(e.message));
  }, [user]);
  const admin = user?.role === "ADMIN";
  const student = user?.role === "STUDENT";
  const title = admin ? "Platform overview" : student ? "Your career dashboard" : "Recruitment workspace";
  const metricData = admin && stats ? [
    ["Total users", stats.users, Users], ["Students", stats.students, GraduationCap], ["Companies", stats.companies, Building2], ["Open opportunities", stats.jobs, BriefcaseBusiness]
  ] : student ? [
    ["Profile strength", "Get started", GraduationCap], ["Recommended roles", "Coming next", Sparkles], ["Applications", "0", FileText], ["Assessments", "0", CheckCircle2]
  ] : [
    ["Active jobs", "0", BriefcaseBusiness], ["Candidates", "0", Users], ["Shortlist", "0", CheckCircle2], ["Interviews", "0", Activity]
  ];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="sidebar-brand"><span className="brand-mark"><Command size={19}/></span><span>TalentOS</span><span className="brand-beta">BETA</span></div>
      <div className="workspace-label">WORKSPACE <ChevronDown size={13}/></div>
      <div className="workspace-switch"><span className="workspace-avatar">{(user?.full_name || "T").slice(0,1).toUpperCase()}</span><span><b>{user?.full_name || "Your workspace"}</b><small>{user?.role?.replace("_"," ")}</small></span><ChevronDown size={15}/></div>
      <nav className="side-nav">
        <p className="nav-caption">OVERVIEW</p><a className="nav-item active"><LayoutDashboard size={17}/> Dashboard</a>
        <a className="nav-item"><BriefcaseBusiness size={17}/> {student ? "Explore jobs" : "Job openings"} <span className="nav-soon">Soon</span></a>
        <a className="nav-item"><Users size={17}/> {student ? "My applications" : "Candidates"} <span className="nav-soon">Soon</span></a>
        <a className="nav-item"><Sparkles size={17}/> AI matching <span className="nav-soon">Soon</span></a>
        <p className="nav-caption nav-caption-spaced">MANAGE</p>
        <a className="nav-item"><FileText size={17}/> Assessments <span className="nav-soon">Soon</span></a>
        <a className="nav-item"><Activity size={17}/> Analytics <span className="nav-soon">Soon</span></a>
        {admin && <a className="nav-item"><ShieldCheck size={17}/> Administration</a>}
      </nav>
      <div className="sidebar-bottom"><div className="help-card"><CircleHelp size={18}/><div><b>Need a hand?</b><small>Explore the platform guide</small></div><ArrowUpRight size={15}/></div><button className="logout-button" onClick={onLogout}><LogOut size={17}/> Sign out</button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <b>Dashboard</b></div><div className="top-actions"><button className="icon-button" aria-label="Search"><Search size={17}/></button><button className="icon-button" aria-label="Notifications"><Bell size={17}/></button><div className="top-avatar">{(user?.full_name || "T").slice(0,1).toUpperCase()}</div></div></header>
      <div className="page-content">
        <div className="welcome-row"><div><p className="eyebrow">MONDAY · YOUR WORKSPACE</p><h1>{title}<span className="heading-period">.</span></h1><p className="muted">Hi {user?.full_name?.split(" ")[0] || "there"}, here's what's happening with your workspace.</p></div><div className="date-pill"><Activity size={15}/> Live workspace</div></div>
        <div className="notice-banner"><div className="notice-icon"><Sparkles size={19}/></div><div><b>Your recruitment copilot is being prepared</b><p>TalentOS is designed to handle repetitive recruiting tasks and explain its recommendations. More workflow modules are coming online in phases.</p></div><span className="notice-status"><span/> Foundation</span></div>
        <div className="section-heading"><div><h2>Workspace snapshot</h2><p>Key information at a glance</p></div><button className="secondary-button" onClick={()=>window.location.reload()}>Refresh <Activity size={14}/></button></div>
        <div className="metric-grid">{metricData.map(([label,value,Icon],i)=><div className="metric-card" key={label}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={17}/></span></div><div className="metric-value">{value}</div><div className="metric-foot">{admin && stats ? "Current platform records" : "Available as modules launch"}</div></div>)}</div>
        {status && <div className="error-message">{status}. Check that the API is running and your account has permission.</div>}
        <div className="content-grid"><section className="panel"><div className="panel-heading"><div><h2>Next steps</h2><p>Get your workspace ready</p></div><span className="tiny-tag">GETTING STARTED</span></div><div className="step-row"><span className="step-number done"><CheckCircle2 size={17}/></span><div><b>Account created</b><p>Your account is ready to use.</p></div><span className="step-state">Complete</span></div><div className="step-row"><span className="step-number"><GraduationCap size={17}/></span><div><b>Complete your profile</b><p>Add your skills, experience, and projects.</p></div><span className="step-state pending">Next</span></div><div className="step-row"><span className="step-number"><Zap size={17}/></span><div><b>Enable smart matching</b><p>AI-powered job matching will be available in a later phase.</p></div><span className="step-state pending">Planned</span></div></section><section className="panel activity-panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>Updates from your workspace</p></div></div><div className="empty-activity"><span className="empty-icon"><Activity size={22}/></span><b>You're all caught up</b><p>New activity will appear here as you use TalentOS.</p></div></section></div>
        <footer className="page-footer"><span>© 2026 TalentOS</span><span><span className="status-dot"/> All systems ready for development</span><a href="https://github.com/Hrsht02/TalentOS" target="_blank" rel="noreferrer">Project repository <ArrowUpRight size={13}/></a></footer>
      </div>
    </main>
  </div>;
}

export default function App() {
  const [user, setUser] = useState(initialUser);
  const [mode, setMode] = useState("login");
  const navigate = useNavigate();
  function logout() { clearSession(); setUser(null); setMode("login"); navigate("/"); }
  if (!user) return <main className="auth-layout"><div className="auth-decoration"><div className="decoration-grid"/><div className="hero-content"><div className="hero-kicker"><Sparkles size={15}/> INTELLIGENT RECRUITMENT</div><h2>Hire for potential.<br/><span>Move with clarity.</span></h2><p>One connected workspace for candidate discovery, skills assessment, and transparent hiring decisions.</p><div className="hero-proof"><div className="proof-avatars"><span>AK</span><span>RS</span><span>JM</span><span>+</span></div><div><b>Built for modern teams</b><small>Students · Employers · Agencies</small></div></div></div><div className="hero-bottom"><span>TalentOS / Recruitment, reimagined</span><span>Designed for people, powered by AI.</span></div></div><section className="auth-side"><AuthPanel mode={mode} onMode={setMode} onSuccess={setUser}/></section></main>;
  return <Dashboard user={user} onLogout={logout}/>;
}
