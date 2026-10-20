import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ArrowRight, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CheckCircle2, ChevronDown, CircleHelp, Command, FileText, GraduationCap, LayoutDashboard, LogOut, Search, ShieldCheck, Sparkles, Users, Zap, UserRound, Plus, Trash2, Save, LockKeyhole } from "lucide-react";
import { apiRequest, clearSession, saveSession } from "./api";
import AssessmentCenter from "./AssessmentCenter.jsx";
import NotificationsCenter from "./NotificationsCenter.jsx";

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
      {isRegister && <><label>I'm joining as<select value={form.role} onChange={(e)=>change("role",e.target.value)}><option value="STUDENT">Student / Candidate</option><option value="COMPANY_HR">Company HR / Recruiter</option><option value="AGENCY_MEMBER">Recruitment agency</option></select></label>
      {form.role === "AGENCY_MEMBER" && <label>Agency name<input required value={form.organization_name} onChange={(e)=>change("organization_name",e.target.value)} placeholder="Agency name"/></label>}
      {form.role === "COMPANY_HR" && <p className="muted">Company profiles are managed by TalentOS. After creating your account, request to join your existing company; its owner will approve or reject your request.</p>}</>}
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
  const [selectedMatchJob, setSelectedMatchJob] = useState(null);
  const [matches, setMatches] = useState([]);
  const [rankingJob, setRankingJob] = useState(null);
  const [ranking, setRanking] = useState([]);
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
  async function runMatching(job) {
    setError(""); setNotice("");
    try {
      const result = await apiRequest("/jobs/" + job.id + "/match", { method: "POST" });
      setSelectedMatchJob(job); setMatches([]);
      setNotice("Candidate matching queued (task " + result.task_id + "). The worker will also calculate applicant scores and shortlist recommendations.");
    } catch (e) { setError(e.message); }
  }
  async function viewMatches(job) {
    setError(""); setNotice("");
    try {
      const result = await apiRequest("/jobs/" + job.id + "/matches?limit=100");
      setSelectedMatchJob(job); setMatches(result);
      setNotice("Loaded " + result.length + " candidate match records.");
    } catch (e) { setError(e.message); }
  }
  async function viewRanking(job) {
    setError(""); setNotice("");
    try {
      const result = await apiRequest("/jobs/" + job.id + "/ranking?limit=100");
      setRankingJob(job); setRanking(result.results || []);
      setNotice(result.count ? "Loaded the latest ranking snapshot." : "No ranking snapshot yet. Run matching and check again when the worker finishes.");
    } catch (e) { setError(e.message); }
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
    <div className="jobs-list">{jobs.map((job)=><article className="job-card" key={job.id}><div className="job-company-icon"><Building2 size={20}/></div><div className="job-main"><div className="job-title-line"><div><h3>{job.title}</h3><small>{job.company_name || "Company workspace"}</small></div><span className={`job-status status-${String(job.status).toLowerCase()}`}>{job.status.replace("_"," ")}</span></div><p className="job-meta">{job.location || "Location not specified"} <span>·</span> {job.employment_type || "Employment type not specified"} <span>·</span> {job.openings} {job.openings === 1 ? "opening" : "openings"}</p><p className="job-description">{job.description}</p><div className="job-tags"><span><CheckCircle2 size={12}/> Employer managed</span><span><Sparkles size={12}/> AI matching planned</span></div></div><div className="job-actions">{employer ? job.status === "DRAFT" || job.status === "PAUSED" ? <button className="primary-button" onClick={()=>publish(job)}>Publish <ArrowUpRight size={14}/></button> : <div className="employer-job-actions"><button className="secondary-button" onClick={()=>viewMatches(job)}>View matches</button><button className="secondary-button" onClick={()=>viewRanking(job)}>View ranking</button><button className="primary-button" onClick={()=>runMatching(job)}><Sparkles size={13}/> Run matching</button></div> : <button className="primary-button" onClick={()=>apply(job)}>Apply now <ArrowRight size={14}/></button>}</div></article>)}
    {rankingJob && employer && <section className="panel matches-panel"><div className="panel-heading"><div><h2>Candidate ranking · {rankingJob.title}</h2><p>Job-related evidence scores and shortlist recommendations. HR retains final decisions.</p></div><span className="tiny-tag">{ranking.length} RANKED</span></div>{ranking.length === 0 ? <p className="profile-empty">No ranking snapshot yet. Run matching and check again when the worker finishes.</p> : <div className="matches-table-wrap"><table className="matches-table"><thead><tr><th>Rank</th><th>Candidate</th><th>Total score</th><th>Eligibility</th><th>Score breakdown</th><th>Shortlist</th></tr></thead><tbody>{ranking.map(item=><tr key={item.application_id}><td><b>#{item.rank}</b></td><td><b>{item.full_name}</b><small>{item.headline || "Headline not added"}{item.location ? " · " + item.location : ""}</small></td><td><span className="match-score">{Math.round(item.score)}%</span></td><td><span className={item.eligible ? "eligibility eligible" : "eligibility review"}>{item.eligible ? "Eligible" : "Ineligible"}</span></td><td>{item.score_breakdown.map(part=><div key={part.criterion} className="ranking-breakdown"><span>{part.criterion}</span><b>{Math.round(part.score)}%</b></div>)}</td><td><span className={item.shortlist_recommended ? "eligibility eligible" : "eligibility review"}>{item.shortlist_recommended ? "Recommended" : "Review"}</span><small>{item.shortlist_decision?.replaceAll("_"," ")}</small></td></tr>)}</tbody></table></div>}</section>}
    {selectedMatchJob && employer && <section className="panel matches-panel"><div className="panel-heading"><div><h2>Candidate matches · {selectedMatchJob.title}</h2><p>Sorted by eligibility and job-related evidence. Review before shortlisting.</p></div><span className="tiny-tag">{matches.length} RESULTS</span></div>{matches.length === 0 ? <p className="profile-empty">No results loaded yet. Run matching and then select View matches again after the worker completes.</p> : <div className="matches-table-wrap"><table className="matches-table"><thead><tr><th>Candidate</th><th>Score</th><th>Eligibility</th><th>Evidence</th><th>Skill gaps</th></tr></thead><tbody>{matches.map(item=><tr key={item.student_id}><td><b>{item.full_name}</b><small>{item.headline || "Headline not added"}{item.location ? " · " + item.location : ""}</small></td><td><span className="match-score">{Math.round(item.score)}%</span></td><td><span className={item.eligible ? "eligibility eligible" : "eligibility review"}>{item.eligible ? "Eligible" : "Review"}</span></td><td>{item.explanation}</td><td>{item.skill_gaps?.length ? item.skill_gaps.join(", ") : "No configured skill gaps"}</td></tr>)}</tbody></table></div>}</section>}
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


function CompanyCenter({ user, onGoJobs }) {
  const [membership, setMembership] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [members, setMembers] = useState([]);
  const [requests, setRequests] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState("");
  const [joinMessage, setJoinMessage] = useState("");
  const [hrForm, setHrForm] = useState({full_name:"",email:"",temporary_password:"",sub_role:"HR"});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setError("");
    try {
      const [m, directory] = await Promise.all([
        apiRequest("/companies/my-membership"),
        apiRequest("/companies/directory")
      ]);
      setMembership(m); setCompanies(directory);
      if (!selectedCompany && directory.length) setSelectedCompany(directory[0].id);
      if (m.has_company && m.can_manage_members) {
        const [memberRows, requestRows] = await Promise.all([
          apiRequest("/companies/mine/members"), apiRequest("/companies/mine/join-requests")
        ]);
        setMembers(memberRows); setRequests(requestRows);
      } else { setMembers([]); setRequests([]); }
    } catch(e) { setError(e.message); }
  }
  useEffect(()=>{ load(); }, []);
  async function requestJoin(event) {
    event.preventDefault(); setError(""); setNotice(""); setBusy(true);
    try {
      const result = await apiRequest("/companies/join-requests", {method:"POST",body:JSON.stringify({company_id:selectedCompany,message:joinMessage || null})});
      setNotice(result.message || "Join request submitted. The company owner must approve it."); setJoinMessage(""); await load();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function decideRequest(id, action) {
    setError(""); setNotice("");
    try { await apiRequest(`/companies/mine/join-requests/${id}/${action}`, {method:"POST"}); setNotice(action === "approve" ? "HR request approved." : "Request rejected."); await load(); }
    catch(e) { setError(e.message); }
  }
  async function addMember(event) {
    event.preventDefault(); setError(""); setNotice(""); setBusy(true);
    try {
      await apiRequest("/companies/mine/members", {method:"POST",body:JSON.stringify(hrForm)});
      setNotice("HR account added. Share the temporary credentials securely and require a password change."); setHrForm({full_name:"",email:"",temporary_password:"",sub_role:"HR"}); await load();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function removeMember(id) {
    if (!window.confirm("Remove this person from the company? Their user account will remain active but lose this company membership.")) return;
    setError(""); setNotice("");
    try { await apiRequest(`/companies/mine/members/${id}`, {method:"DELETE"}); setNotice("Company membership removed."); await load(); }
    catch(e) { setError(e.message); }
  }
  return <div className="jobs-view">
    <div className="welcome-row"><div><p className="eyebrow">COMPANY WORKSPACE</p><h1>Company & team<span className="heading-period">.</span></h1><p className="muted">Company profiles are platform-managed. Owners approve HR membership and manage the recruiting team.</p></div>{membership?.has_company && <button className="primary-button" onClick={onGoJobs}><BriefcaseBusiness size={15}/> Manage job posts</button>}</div>
    {error && <div className="error-message jobs-message">{error}</div>}{notice && <div className="success-message jobs-message">{notice}</div>}
    {!membership?.has_company ? <section className="panel"><div className="panel-heading"><div><h2>{membership?.pending_request ? "Join request pending" : "Request to join your company"}</h2><p>{membership?.pending_request ? `Your request to ${membership.pending_request.company_name} is awaiting owner approval.` : "Select the company you work for. Its owner will approve or reject your request."}</p></div></div>
      {!membership?.pending_request && <form className="project-add-form" onSubmit={requestJoin}><label>Company<select required value={selectedCompany} onChange={e=>setSelectedCompany(e.target.value)}>{companies.map(c=><option key={c.id} value={c.id}>{c.name}{c.verified ? " · Verified" : ""}</option>)}</select></label><label>Message to company owner (optional)<textarea rows="3" maxLength="1000" value={joinMessage} onChange={e=>setJoinMessage(e.target.value)} placeholder="Your role and why you need access"/></label><button className="primary-button" disabled={busy || !selectedCompany}>{busy ? "Submitting…" : "Request to join"} <ArrowRight size={15}/></button></form>}
      {companies.length===0 && <p className="profile-empty">No company profiles are available yet. Ask the TalentOS platform administrator to provision your company.</p>}
    </section> : <>
      <section className="panel"><div className="panel-heading"><div><h2>{membership.company.name}</h2><p>Membership role: {membership.sub_role}. Job posts and candidate records are scoped to this company.</p></div><span className="tiny-tag">{membership.can_manage_members ? "OWNER / ADMIN" : "HR MEMBER"}</span></div><button className="primary-button" onClick={onGoJobs}><BriefcaseBusiness size={15}/> Create or manage job posts</button></section>
      {membership.can_manage_members && <>
        <section className="panel"><div className="panel-heading"><div><h2>Pending HR join requests</h2><p>Approve only people who should have access to this company's recruitment workspace.</p></div><span className="tiny-tag">{requests.length} PENDING</span></div>
          {requests.length===0 ? <p className="profile-empty">No pending requests.</p> : requests.map(r=><div className="step-row" key={r.id}><div><b>{r.full_name}</b><p>{r.email}{r.message ? " · "+r.message : ""}</p></div><div className="employer-job-actions"><button className="primary-button" onClick={()=>decideRequest(r.id,"approve")}>Approve</button><button className="secondary-button" onClick={()=>decideRequest(r.id,"reject")}>Reject</button></div></div>)}
        </section>
        <section className="panel"><div className="panel-heading"><div><h2>Company team</h2><p>Add HR accounts or remove active company membership. Temporary passwords must be changed at first login.</p></div><span className="tiny-tag">{members.length} MEMBERS</span></div>
          {members.map(m=><div className="step-row" key={m.membership_id}><div><b>{m.full_name}</b><p>{m.email} · {m.sub_role}{m.must_change_password ? " · password change required" : ""}</p></div>{m.sub_role!=="OWNER" && <button className="secondary-button" onClick={()=>removeMember(m.user_id)}>Remove</button>}</div>)}
          <form className="project-add-form" onSubmit={addMember}><h3>Add HR / recruiter</h3><div className="form-grid"><label>Full name<input required minLength="2" value={hrForm.full_name} onChange={e=>setHrForm({...hrForm,full_name:e.target.value})}/></label><label>Email<input required type="email" value={hrForm.email} onChange={e=>setHrForm({...hrForm,email:e.target.value})}/></label><label>Temporary password<input required minLength="12" type="password" value={hrForm.temporary_password} onChange={e=>setHrForm({...hrForm,temporary_password:e.target.value})}/></label><label>Role<select value={hrForm.sub_role} onChange={e=>setHrForm({...hrForm,sub_role:e.target.value})}><option value="HR">HR / Recruiter</option><option value="ADMIN">Company admin</option></select></label></div><button className="primary-button" disabled={busy}>{busy ? "Adding…" : "Add team member"} <Plus size={14}/></button></form>
        </section>
      </>}
    </>}
  </div>;
}

function AdminCompaniesCenter() {
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({name:"",description:"",website:"",owner_name:"",owner_email:"",temporary_password:""});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() { try { setCompanies(await apiRequest("/companies/directory")); } catch(e) { setError(e.message); } }
  useEffect(()=>{ load(); },[]);
  async function create(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/companies/admin/create",{method:"POST",body:JSON.stringify(form)});
      setNotice(`Created ${result.company} and owner account ${result.owner_email}. Share the temporary password privately; it must be changed at first login.`);
      setForm({name:"",description:"",website:"",owner_name:"",owner_email:"",temporary_password:""}); await load();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  return <div className="jobs-view"><div className="welcome-row"><div><p className="eyebrow">PLATFORM ADMINISTRATION</p><h1>Company provisioning<span className="heading-period">.</span></h1><p className="muted">Create verified company profiles and hand owner credentials to the organisation. Public HR registration cannot create company records.</p></div></div>
    {error && <div className="error-message jobs-message">{error}</div>}{notice && <div className="success-message jobs-message">{notice}</div>}
    <form className="panel project-add-form" onSubmit={create}><div className="panel-heading"><div><h2>Create company profile</h2><p>Owner accounts are activated and forced to change their temporary password after first login.</p></div></div>
      <div className="form-grid"><label>Company name<input required minLength="2" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Website<input type="url" value={form.website} onChange={e=>setForm({...form,website:e.target.value})} placeholder="https://example.com"/></label><label>Owner full name<input required minLength="2" value={form.owner_name} onChange={e=>setForm({...form,owner_name:e.target.value})}/></label><label>Owner email<input required type="email" value={form.owner_email} onChange={e=>setForm({...form,owner_email:e.target.value})}/></label><label>Temporary password<input required minLength="12" type="password" value={form.temporary_password} onChange={e=>setForm({...form,temporary_password:e.target.value})}/></label></div><label>Company description<textarea rows="3" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><button className="primary-button" disabled={busy}>{busy ? "Creating…" : "Create company and owner"} <ArrowRight size={15}/></button>
    </form><section className="panel"><div className="panel-heading"><div><h2>Company directory</h2><p>Profiles already provisioned by the platform.</p></div><span className="tiny-tag">{companies.length} COMPANIES</span></div>{companies.map(c=><div className="step-row" key={c.id}><div><b>{c.name}</b><p>{c.description || c.slug}</p></div><span className="job-status status-published">{c.verified ? "VERIFIED" : "PENDING"}</span></div>)}</section>
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
  const [view, setView] = useState(user?.role === "COMPANY_HR" ? "company" : "dashboard");
  const [automationBusy, setAutomationBusy] = useState(false);
  const [automationMessage, setAutomationMessage] = useState("");
  async function loadAdminStats() {
    if (user?.role !== "ADMIN") return;
    setStatus("");
    try { setStats(await apiRequest("/admin/overview")); }
    catch (e) { setStats(null); setStatus(e.message || "Could not load platform statistics."); }
  }
  useEffect(() => { loadAdminStats(); }, [user?.id, user?.role]);
  const admin = user?.role === "ADMIN";
  const student = user?.role === "STUDENT";
  async function runAutomationNow() {
    setAutomationBusy(true); setAutomationMessage("");
    try {
      const result = await apiRequest("/admin/automation/run", { method: "POST" });
      setAutomationMessage("Automation queued successfully. Task ID: " + result.task_id + ". The Render worker must be running.");
    } catch (e) { setAutomationMessage(e.message || "Could not queue automation."); }
    finally { setAutomationBusy(false); }
  }
  const title = admin ? "Platform overview" : student ? "Your career dashboard" : "Recruitment workspace";
  const metricData = admin ? [
    ["Total users", stats ? stats.users : "—", Users], ["Students", stats ? stats.students : "—", GraduationCap], ["Companies", stats ? stats.companies : "—", Building2], ["Jobs", stats ? stats.jobs : "—", BriefcaseBusiness]
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
        <button className={`nav-item ${view === "notifications" ? "active" : ""}`} onClick={()=>setView("notifications")}><Bell size={17}/> Notifications</button>
        {user?.role === "COMPANY_HR" && <button className={`nav-item ${view === "company" ? "active" : ""}`} onClick={()=>setView("company")}><Building2 size={17}/> Company & team</button>}
        {student && <button className={`nav-item ${view === "profile" ? "active" : ""}`} onClick={()=>setView("profile")}><UserRound size={17}/> My profile</button>}
        <a className="nav-item"><Users size={17}/> {student ? "My applications" : "Candidates"} <span className="nav-soon">Soon</span></a>
        <a className="nav-item"><Sparkles size={17}/> AI matching <span className="nav-soon">Soon</span></a>
        <p className="nav-caption nav-caption-spaced">MANAGE</p>
        <button className={`nav-item ${view === "assessments" ? "active" : ""}`} onClick={()=>setView("assessments")}><FileText size={17}/> Assessments</button>
        <a className="nav-item"><Activity size={17}/> Analytics <span className="nav-soon">Soon</span></a>
        {admin && <button className={`nav-item ${view === "admin-companies" ? "active" : ""}`} onClick={()=>setView("admin-companies")}><ShieldCheck size={17}/> Administration</button>}
      </nav>
      <div className="sidebar-bottom"><div className="help-card"><CircleHelp size={18}/><div><b>Need a hand?</b><small>Explore the platform guide</small></div><ArrowUpRight size={15}/></div><button className="logout-button" onClick={onLogout}><LogOut size={17}/> Sign out</button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <b>{view === "jobs" ? "Job openings" : view === "profile" ? "My profile" : view === "assessments" ? "Assessments" : "Dashboard"}</b></div><div className="top-actions"><button className="icon-button" aria-label="Search"><Search size={17}/></button><button className="icon-button" aria-label="Notifications" onClick={()=>setView("notifications")}><Bell size={17}/></button><div className="top-avatar">{(user?.full_name || "T").slice(0,1).toUpperCase()}</div></div></header>
      <div className="page-content">
        {user?.must_change_password && <ChangePasswordPanel user={user} onUpdated={onUserUpdate}/>}
        {view === "notifications" ? <NotificationsCenter/> : view === "jobs" ? <JobCenter user={user}/> : view === "company" && user?.role === "COMPANY_HR" ? <CompanyCenter user={user} onGoJobs={()=>setView("jobs")}/> : view === "admin-companies" && admin ? <AdminCompaniesCenter/> : view === "profile" && student ? <ProfileCenter/> : view === "assessments" ? <AssessmentCenter user={user}/> : <>
        <div className="welcome-row"><div><p className="eyebrow">MONDAY · YOUR WORKSPACE</p><h1>{title}<span className="heading-period">.</span></h1><p className="muted">Hi {user?.full_name?.split(" ")[0] || "there"}, here's what's happening with your workspace.</p></div><div className="date-pill"><Activity size={15}/> Live workspace</div></div>
        <div className="notice-banner"><div className="notice-icon"><Sparkles size={19}/></div><div><b>Your recruitment copilot is being prepared</b><p>TalentOS is designed to handle repetitive recruiting tasks and explain its recommendations. More workflow modules are coming online in phases.</p></div><span className="notice-status"><span/> Foundation</span></div>
        <div className="section-heading"><div><h2>Workspace snapshot</h2><p>Key information at a glance</p></div><button className="secondary-button" onClick={admin ? loadAdminStats : ()=>window.location.reload()}>Refresh <Activity size={14}/></button></div>
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
