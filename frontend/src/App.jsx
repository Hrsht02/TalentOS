import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ArrowRight, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CheckCircle2, ChevronDown, CircleHelp, Command, FileText, GraduationCap, LayoutDashboard, LogOut, Search, ShieldCheck, Sparkles, Users, Zap, UserRound, Plus, Trash2, Save, LockKeyhole } from "lucide-react";
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

function JobCenter({ user }) {
  const [jobs, setJobs] = useState([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const employer = user?.role === "COMPANY_HR";
  const [form, setForm] = useState({ title: "", description: "", location: "", employment_type: "Full-time", openings: 1 });
  async function loadJobs() {
    setError("");
    try { setJobs(await apiRequest(employer ? "/jobs/mine" : `/jobs?q=${encodeURIComponent(query)}`)); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { loadJobs(); }, [user?.role]);
  async function createJob(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest("/jobs", { method: "POST", body: JSON.stringify({ ...form, openings: Number(form.openings) }) });
      setNotice("Draft saved. Review it and publish when ready.");
      setShowCreate(false); setForm({ title: "", description: "", location: "", employment_type: "Full-time", openings: 1 }); await loadJobs();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function publish(job) {
    setError(""); setNotice("");
    try { await apiRequest(`/jobs/${job.id}/publish`, { method: "POST" }); setNotice("Job published successfully."); await loadJobs(); }
    catch (e) { setError(e.message); }
  }
  async function apply(job) {
    setError(""); setNotice("");
    try { await apiRequest(`/jobs/${job.id}/apply`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } }); setNotice(`Application submitted for ${job.title}.`); }
    catch (e) { setError(e.message); }
  }
  return <div className="jobs-view">
    <div className="welcome-row"><div><p className="eyebrow">OPPORTUNITY EXPLORER</p><h1>{employer ? "Manage job openings" : "Find your next opportunity"}<span className="heading-period">.</span></h1><p className="muted">{employer ? "Create openings, publish roles, and keep hiring moving." : "Explore published roles and apply with your TalentOS profile."}</p></div>{employer && <button className="primary-button" onClick={()=>setShowCreate(!showCreate)}><BriefcaseBusiness size={15}/>{showCreate ? "Cancel" : "Create job"}</button>}</div>
    <div className="jobs-toolbar"><div className="jobs-search"><Search size={16}/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Search job titles"/><button className="secondary-button" onClick={loadJobs}>Search</button></div><span className="jobs-count">{jobs.length} {jobs.length === 1 ? "role" : "roles"}</span></div>
    {error && <div className="error-message jobs-message">{error}</div>}{notice && <div className="success-message jobs-message">{notice}</div>}
    {showCreate && employer && <form className="panel create-job-form" onSubmit={createJob}><div className="panel-heading"><div><h2>New job opening</h2><p>Start with the essentials. You can publish after saving.</p></div></div><div className="form-grid"><label>Job title<input required minLength="3" value={form.title} onChange={(e)=>setForm({...form,title:e.target.value})} placeholder="e.g. Frontend Engineer"/></label><label>Location<input value={form.location} onChange={(e)=>setForm({...form,location:e.target.value})} placeholder="Remote / Patna / Bengaluru"/></label><label>Employment type<select value={form.employment_type} onChange={(e)=>setForm({...form,employment_type:e.target.value})}><option>Full-time</option><option>Internship</option><option>Contract</option><option>Part-time</option></select></label><label>Openings<input type="number" min="1" max="10000" value={form.openings} onChange={(e)=>setForm({...form,openings:e.target.value})}/></label></div><label className="description-label">Job description<textarea required minLength="30" rows="5" value={form.description} onChange={(e)=>setForm({...form,description:e.target.value})} placeholder="Describe the role, responsibilities, and skills required…"/></label><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Save draft"} <ArrowRight size={15}/></button></form>}
    <div className="jobs-list">{jobs.map((job)=><article className="job-card" key={job.id}><div className="job-company-icon"><Building2 size={20}/></div><div className="job-main"><div className="job-title-line"><h3>{job.title}</h3><span className={`job-status status-${String(job.status).toLowerCase()}`}>{job.status.replace("_"," ")}</span></div><p className="job-meta">{job.location || "Location not specified"} <span>·</span> {job.employment_type || "Employment type not specified"} <span>·</span> {job.openings} {job.openings === 1 ? "opening" : "openings"}</p><p className="job-description">{job.description}</p><div className="job-tags"><span><CheckCircle2 size={12}/> Employer managed</span><span><Sparkles size={12}/> AI matching planned</span></div></div><div className="job-actions">{employer ? job.status === "DRAFT" || job.status === "PAUSED" ? <button className="primary-button" onClick={()=>publish(job)}>Publish <ArrowUpRight size={14}/></button> : <span className="job-status status-published">Live role</span> : <button className="primary-button" onClick={()=>apply(job)}>Apply now <ArrowRight size={14}/></button>}</div></article>)}
    {jobs.length === 0 && <div className="panel empty-jobs"><span className="empty-icon"><BriefcaseBusiness size={22}/></span><h3>{employer ? "No job openings yet" : "No matching jobs yet"}</h3><p>{employer ? "Create your first draft to start building your hiring pipeline." : "Try another search, or check back as employers publish new roles."}</p>{employer && <button className="primary-button" onClick={()=>setShowCreate(true)}>Create your first job</button>}</div>}</div>
  </div>;
}

function ProfileCenter() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({});
  const [skill, setSkill] = useState({ skill: "", proficiency: "Intermediate", years_experience: "" });
  const [project, setProject] = useState({ name: "", description: "", repository_url: "", technologies: "" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    try { const data = await apiRequest("/student/profile"); setProfile(data); setForm({
      headline: data.headline || "", phone: data.phone || "", location: data.location || "",
      graduation_year: data.graduation_year || "", degree: data.degree || "", branch: data.branch || "",
      cgpa: data.cgpa ?? "", backlogs: data.backlogs ?? "", expected_salary_min: data.expected_salary_min ?? "",
      expected_salary_max: data.expected_salary_max ?? ""
    }); } catch(e) { setError(e.message); }
  }
  useEffect(()=>{ load(); }, []);
  async function saveProfile(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const body = { ...form };
    ["graduation_year","cgpa","backlogs","expected_salary_min","expected_salary_max"].forEach(k => body[k] === "" ? body[k] = null : body[k] = Number(body[k]));
    try { await apiRequest("/student/profile", { method:"PATCH", body:JSON.stringify(body) }); setNotice("Profile saved."); await load(); }
    catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function addSkill(event) {
    event.preventDefault(); setError(""); setNotice("");
    try { await apiRequest("/student/profile/skills", { method:"POST", body:JSON.stringify({ ...skill, years_experience: skill.years_experience === "" ? null : Number(skill.years_experience) }) }); setSkill({skill:"",proficiency:"Intermediate",years_experience:""}); setNotice("Skill saved."); await load(); }
    catch(e) { setError(e.message); }
  }
  async function addProject(event) {
    event.preventDefault(); setError(""); setNotice("");
    try { await apiRequest("/student/profile/projects", { method:"POST", body:JSON.stringify({ ...project, technologies:project.technologies.split(",").map(x=>x.trim()).filter(Boolean) }) }); setProject({name:"",description:"",repository_url:"",technologies:""}); setNotice("Project saved."); await load(); }
    catch(e) { setError(e.message); }
  }
  async function removeItem(path) {
    setError(""); setNotice("");
    try { await apiRequest(path, { method:"DELETE" }); setNotice("Item removed."); await load(); } catch(e) { setError(e.message); }
  }
  const change = (key,value) => setForm(old=>({...old,[key]:value}));
  if (!profile && !error) return <div className="panel">Loading your profile…</div>;
  return <div className="profile-view">
    <div className="welcome-row"><div><p className="eyebrow">YOUR PROFESSIONAL STORY</p><h1>Student profile<span className="heading-period">.</span></h1><p className="muted">Keep your skills and projects up to date so future matching can use accurate information.</p></div><div className="profile-completion"><b>{profile?.profile_completion ?? 0}%</b><span>profile strength</span><div><i style={{width:`${profile?.profile_completion ?? 0}%`}}/></div></div></div>
    {error && <div className="error-message jobs-message">{error}</div>}{notice && <div className="success-message jobs-message">{notice}</div>}
    {profile && <>
      <form className="panel profile-form" onSubmit={saveProfile}><div className="panel-heading"><div><h2>Basic information</h2><p>{profile.full_name} · {profile.email}</p></div><button className="primary-button" disabled={busy}><Save size={14}/>{busy ? "Saving…" : "Save profile"}</button></div>
      <label className="wide-label">Professional headline<input value={form.headline} onChange={e=>change("headline",e.target.value)} placeholder="e.g. Computer Science student interested in AI"/></label>
      <div className="form-grid"><label>Phone<input value={form.phone} onChange={e=>change("phone",e.target.value)} placeholder="Phone number"/></label><label>Location<input value={form.location} onChange={e=>change("location",e.target.value)} placeholder="City, country or remote"/></label><label>Degree<input value={form.degree} onChange={e=>change("degree",e.target.value)} placeholder="Degree"/></label><label>Branch / specialization<input value={form.branch} onChange={e=>change("branch",e.target.value)} placeholder="Computer Science, etc."/></label><label>Graduation year<input type="number" min="1950" max="2100" value={form.graduation_year} onChange={e=>change("graduation_year",e.target.value)} placeholder="2027"/></label><label>CGPA (out of 10)<input type="number" min="0" max="10" step=".01" value={form.cgpa} onChange={e=>change("cgpa",e.target.value)} placeholder="8.5"/></label><label>Backlogs<input type="number" min="0" value={form.backlogs} onChange={e=>change("backlogs",e.target.value)} placeholder="0"/></label><label>Minimum expected salary<input type="number" min="0" value={form.expected_salary_min} onChange={e=>change("expected_salary_min",e.target.value)} placeholder="Optional"/></label></div></form>
      <div className="profile-columns"><section className="panel"><div className="panel-heading"><div><h2>Skills</h2><p>Skills can later be matched to job requirements.</p></div><span className="tiny-tag">{profile.skills.length} ADDED</span></div><form className="inline-add-form" onSubmit={addSkill}><input required value={skill.skill} onChange={e=>setSkill({...skill,skill:e.target.value})} placeholder="Add a skill e.g. Python"/><select value={skill.proficiency} onChange={e=>setSkill({...skill,proficiency:e.target.value})}><option>Beginner</option><option>Intermediate</option><option>Advanced</option><option>Expert</option></select><button className="primary-button" aria-label="Add skill"><Plus size={15}/></button></form><div className="skill-list">{profile.skills.map(item=><div className="skill-chip" key={item.id}><span><b>{item.skill}</b><small>{item.proficiency || "Level not set"}</small></span><button aria-label={`Remove ${item.skill}`} onClick={()=>removeItem(`/student/profile/skills/${item.id}`)}><Trash2 size={14}/></button></div>)}{profile.skills.length===0 && <p className="profile-empty">Add your first skill to improve your profile.</p>}</div></section>
      <section className="panel"><div className="panel-heading"><div><h2>Projects</h2><p>Show the work you've built.</p></div><span className="tiny-tag">{profile.projects.length} ADDED</span></div><form className="project-add-form" onSubmit={addProject}><input required value={project.name} onChange={e=>setProject({...project,name:e.target.value})} placeholder="Project name"/><textarea rows="2" value={project.description} onChange={e=>setProject({...project,description:e.target.value})} placeholder="What did you build?"/><input value={project.repository_url} onChange={e=>setProject({...project,repository_url:e.target.value})} placeholder="Repository URL (optional)"/><input value={project.technologies} onChange={e=>setProject({...project,technologies:e.target.value})} placeholder="Technologies, comma separated"/><button className="primary-button"><Plus size={14}/> Add project</button></form><div className="project-list">{profile.projects.map(item=><div className="project-item" key={item.id}><div><b>{item.name}</b><p>{item.description || "No description added"}</p>{item.technologies?.length>0 && <small>{item.technologies.join(" · ")}</small>}</div><button aria-label={`Remove ${item.name}`} onClick={()=>removeItem(`/student/profile/projects/${item.id}`)}><Trash2 size={14}/></button></div>)}</div></section></div>
    </>}
  </div>;
}

function ChangePasswordPanel({ user, onUpdated }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(""); setDone(false);
    if (next !== confirm) { setError("New passwords do not match."); return; }
    if (current === next) { setError("Choose a new password different from the current one."); return; }
    setBusy(true);
    try {
      await apiRequest("/auth/change-password", { method:"POST", body:JSON.stringify({current_password:current,new_password:next}) });
      const updated = {...user, must_change_password:false};
      localStorage.setItem("talentos_user", JSON.stringify(updated));
      onUpdated(updated); setCurrent(""); setNext(""); setConfirm(""); setDone(true);
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  return <section className="password-panel"><div className="password-panel-icon"><LockKeyhole size={18}/></div><div className="password-panel-body"><b>Change your temporary password</b><p>This account was created with a temporary password. Set a new one before continuing with admin tasks.</p>{done && <div className="success-message">Password changed successfully.</div>}{error && <div className="error-message">{error}</div>}<form onSubmit={submit} className="password-form"><input required type="password" value={current} onChange={e=>setCurrent(e.target.value)} placeholder="Current password"/><input required minLength="12" type="password" value={next} onChange={e=>setNext(e.target.value)} placeholder="New password (12+ characters)"/><input required minLength="12" type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder="Confirm new password"/><button className="primary-button" disabled={busy}>{busy ? "Updating…" : "Update password"}</button></form></div></section>;
}

function Dashboard({ user, onLogout, onUserUpdate }) {
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState("");
  const [view, setView] = useState("dashboard");
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
        <p className="nav-caption">OVERVIEW</p><button className={`nav-item ${view === "dashboard" ? "active" : ""}`} onClick={()=>setView("dashboard")}><LayoutDashboard size={17}/> Dashboard</button>
        <button className={`nav-item ${view === "jobs" ? "active" : ""}`} onClick={()=>setView("jobs")}><BriefcaseBusiness size={17}/> {student ? "Explore jobs" : "Job openings"}</button>
        {student && <button className={`nav-item ${view === "profile" ? "active" : ""}`} onClick={()=>setView("profile")}><UserRound size={17}/> My profile</button>}
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
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <b>{view === "jobs" ? "Job openings" : "Dashboard"}</b></div><div className="top-actions"><button className="icon-button" aria-label="Search"><Search size={17}/></button><button className="icon-button" aria-label="Notifications"><Bell size={17}/></button><div className="top-avatar">{(user?.full_name || "T").slice(0,1).toUpperCase()}</div></div></header>
      <div className="page-content">
        {view === "jobs" ? <JobCenter user={user}/> : view === "profile" && student ? <ProfileCenter/> : <>
        <div className="welcome-row"><div><p className="eyebrow">MONDAY · YOUR WORKSPACE</p><h1>{title}<span className="heading-period">.</span></h1><p className="muted">Hi {user?.full_name?.split(" ")[0] || "there"}, here's what's happening with your workspace.</p></div><div className="date-pill"><Activity size={15}/> Live workspace</div></div>
        {user?.must_change_password && <ChangePasswordPanel user={user} onUpdated={onUserUpdate}/>}
        <div className="notice-banner"><div className="notice-icon"><Sparkles size={19}/></div><div><b>Your recruitment copilot is being prepared</b><p>TalentOS is designed to handle repetitive recruiting tasks and explain its recommendations. More workflow modules are coming online in phases.</p></div><span className="notice-status"><span/> Foundation</span></div>
        <div className="section-heading"><div><h2>Workspace snapshot</h2><p>Key information at a glance</p></div><button className="secondary-button" onClick={()=>window.location.reload()}>Refresh <Activity size={14}/></button></div>
        <div className="metric-grid">{metricData.map(([label,value,Icon],i)=><div className="metric-card" key={label}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon size={17}/></span></div><div className="metric-value">{value}</div><div className="metric-foot">{admin && stats ? "Current platform records" : "Available as modules launch"}</div></div>)}</div>
        {status && <div className="error-message">{status}. Check that the API is running and your account has permission.</div>}
        <div className="content-grid"><section className="panel"><div className="panel-heading"><div><h2>Next steps</h2><p>Get your workspace ready</p></div><span className="tiny-tag">GETTING STARTED</span></div><div className="step-row"><span className="step-number done"><CheckCircle2 size={17}/></span><div><b>Account created</b><p>Your account is ready to use.</p></div><span className="step-state">Complete</span></div><div className="step-row"><span className="step-number"><GraduationCap size={17}/></span><div><b>Complete your profile</b><p>Add your skills, experience, and projects.</p></div><span className="step-state pending">Next</span></div><div className="step-row"><span className="step-number"><Zap size={17}/></span><div><b>Enable smart matching</b><p>AI-powered job matching will be available in a later phase.</p></div><span className="step-state pending">Planned</span></div></section><section className="panel activity-panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>Updates from your workspace</p></div></div><div className="empty-activity"><span className="empty-icon"><Activity size={22}/></span><b>You're all caught up</b><p>New activity will appear here as you use TalentOS.</p></div></section></div>
        <footer className="page-footer"><span>© 2026 TalentOS</span><span><span className="status-dot"/> All systems ready for development</span><a href="https://github.com/Hrsht02/TalentOS" target="_blank" rel="noreferrer">Project repository <ArrowUpRight size={13}/></a></footer>
        </>}
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
  return <Dashboard user={user} onLogout={logout} onUserUpdate={setUser}/>;
}
