import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, CheckCircle2, ClipboardList, Code2, Plus, RefreshCw, Send, Sparkles } from "lucide-react";
import { apiRequest } from "./api";

function Alert({ error, notice }) {
  return <>{error && <div className="error-message jobs-message">{error}</div>}{notice && <div className="success-message jobs-message">{notice}</div>}</>;
}

function StudentAssessments() {
  const [invites, setInvites] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState(null);
  const [answers, setAnswers] = useState({});
  const [aptitudeSubmitted, setAptitudeSubmitted] = useState(false);
  const [code, setCode] = useState({});
  const [languages, setLanguages] = useState({});
  const [submissions, setSubmissions] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const active = detail?.status === "IN_PROGRESS";

  async function loadInvites() {
    setError("");
    try { setInvites(await apiRequest("/assessments/my-invites")); }
    catch (e) { setError(e.message); }
  }
  async function openInvite(id) {
    setError(""); setNotice(""); setSelectedId(id); setDetail(null); setAnswers({}); setAptitudeSubmitted(false); setSubmissions({});
    try { setDetail(await apiRequest("/assessments/invites/" + id)); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { loadInvites(); }, []);

  useEffect(() => {
    const pending = Object.entries(submissions).filter(([, value]) => value.status === "QUEUED" || value.status === "RUNNING");
    if (!pending.length) return undefined;
    const timer = setInterval(async () => {
      const updates = await Promise.all(pending.map(async ([questionId, value]) => {
        try { return [questionId, await apiRequest("/assessments/coding-submissions/" + value.submission_id)]; }
        catch { return [questionId, null]; }
      }));
      setSubmissions(old => {
        const next = { ...old };
        updates.forEach(([questionId, value]) => { if (value) next[questionId] = { ...next[questionId], ...value }; });
        return next;
      });
    }, 2500);
    return () => clearInterval(timer);
  }, [submissions]);

  async function start() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/assessments/invites/" + selectedId + "/start", { method: "POST" });
      setDetail(old => ({ ...old, status: "IN_PROGRESS" }));
      setNotice("Attempt " + result.attempt_number + " started. Your timer is running.");
      await loadInvites();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function submitAptitude() {
    setBusy(true); setError(""); setNotice("");
    try {
      const normalized = {};
      Object.entries(answers).forEach(([id, answer]) => { if (answer) normalized[id] = answer; });
      const result = await apiRequest("/assessments/invites/" + selectedId + "/submit", {
        method: "POST", body: JSON.stringify({ answers: normalized }),
      });
      setNotice(result.status === "aptitude_submitted"
        ? "Aptitude section saved. Submit every coding question, wait for results, then finish the assessment."
        : "Aptitude assessment submitted. Score: " + result.score + "%");
      setAptitudeSubmitted(true);
      if (result.status === "submitted") setDetail(old => ({ ...old, status: "SUBMITTED" }));
      await loadInvites();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function submitCode(question) {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/assessments/invites/" + selectedId + "/coding-submissions", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          coding_question_id: question.id,
          language: languages[question.id] || "python",
          source_code: code[question.id] || question.starter_code?.[languages[question.id] || "python"] || "",
        }),
      });
      setSubmissions(old => ({ ...old, [question.id]: { submission_id: result.submission_id, status: result.status } }));
      setNotice("Code queued for evaluation. Results will update automatically.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function finish() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/assessments/invites/" + selectedId + "/finish", { method: "POST" });
      setNotice("Assessment submitted. Final score: " + result.score + "%");
      setDetail(old => ({ ...old, status: "SUBMITTED", final_result: result }));
      await loadInvites();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  const codingQuestions = detail?.coding_questions || [];
  const codingComplete = codingQuestions.length > 0 && codingQuestions.every(q => submissions[q.id]?.result);
  const canFinish = codingComplete && (detail?.assessment?.assessment_type !== "MIXED" || !detail?.aptitude_questions?.length || aptitudeSubmitted);
  return <div className="assessment-view">
    <div className="welcome-row"><div><p className="eyebrow">YOUR EVALUATION WORKSPACE</p><h1>Assessments<span className="heading-period">.</span></h1><p className="muted">Complete employer-assigned aptitude and coding rounds. Your submitted answers are evaluated against the configured rubric.</p></div><button className="secondary-button" onClick={loadInvites}><RefreshCw size={14}/> Refresh</button></div>
    <Alert error={error} notice={notice}/>
    <div className="assessment-layout">
      <section className="panel assessment-invite-list">
        <div className="panel-heading"><div><h2>Your invitations</h2><p>{invites.length} assigned assessment{invites.length === 1 ? "" : "s"}</p></div><span className="tiny-tag">CANDIDATE</span></div>
        {invites.length === 0 && <div className="empty-jobs"><span className="empty-icon"><ClipboardList size={21}/></span><h3>No assessments assigned</h3><p>When a recruiter invites you to an assessment, it will appear here.</p></div>}
        {invites.map(invite => <button className={"assessment-invite " + (selectedId === invite.id ? "selected" : "")} key={invite.id} onClick={() => openInvite(invite.id)}>
          <span className="assessment-invite-icon"><ClipboardList size={17}/></span><span className="assessment-invite-copy"><b>{invite.assessment.title}</b><small>{invite.assessment.assessment_type} · {invite.assessment.duration_minutes} min</small><small>Due {new Date(invite.deadline).toLocaleString()}</small></span><span className={"job-status status-" + invite.status.toLowerCase()}>{invite.status.replaceAll("_", " ")}</span>
        </button>)}
      </section>
      <section className="panel assessment-detail">
        {!detail && <div className="empty-activity"><span className="empty-icon"><Sparkles size={22}/></span><b>Select an assessment</b><p>Review instructions and start your attempt when you're ready.</p></div>}
        {detail && <>
          <div className="panel-heading"><div><h2>{detail.assessment.title}</h2><p>{detail.assessment.assessment_type} · {detail.assessment.duration_minutes} minutes · {detail.assessment.max_attempts} maximum attempt(s)</p></div><span className="tiny-tag">{detail.status.replaceAll("_", " ")}</span></div>
          <div className="assessment-instructions"><b>Before you begin</b><p>Starting an attempt begins the time limit. Keep this page open, answer independently, and submit before the deadline. Hidden coding test cases are not shown to candidates.</p><small>Invitation deadline: {new Date(detail.deadline).toLocaleString()}</small></div>
          {detail.status !== "IN_PROGRESS" && detail.status !== "SUBMITTED" && detail.status !== "COMPLETED" && detail.status !== "EXPIRED" && detail.status !== "CANCELLED" && <button className="primary-button" disabled={busy} onClick={start}>Start assessment <ArrowRight size={15}/></button>}
          {detail.aptitude_questions?.length > 0 && <section className="assessment-section"><div className="section-heading"><div><h2>Aptitude questions</h2><p>{detail.aptitude_questions.length} questions</p></div></div>
            {detail.aptitude_questions.map((q, index) => <article className="assessment-question" key={q.id}><div className="question-number">QUESTION {index + 1} · {q.difficulty} · {q.marks} mark(s)</div><h3>{q.prompt}</h3><div className="question-options">{q.options.map(option => <label key={option.id} className={"question-option " + (answers[q.id] === option.id ? "chosen" : "")}><input type="radio" name={q.id} value={option.id} checked={answers[q.id] === option.id} disabled={!active || aptitudeSubmitted} onChange={() => setAnswers(old => ({ ...old, [q.id]: option.id }))}/><span>{option.id}</span>{option.text}</label>)}</div></article>)}
            {active && !aptitudeSubmitted && <button className="primary-button" disabled={busy} onClick={submitAptitude}>Submit aptitude answers <Send size={14}/></button>}{aptitudeSubmitted && <p className="success-message">Aptitude section submitted.</p>}
          </section>}
          {codingQuestions.length > 0 && <section className="assessment-section"><div className="section-heading"><div><h2>Coding challenges</h2><p>Submit each solution for isolated execution against hidden test cases.</p></div></div>
            {codingQuestions.map((q, index) => <article className="assessment-question coding-question" key={q.id}><div className="question-number">CHALLENGE {index + 1} · {q.difficulty}</div><h3>{q.title}</h3><p className="coding-statement">{q.statement}</p>{q.constraints_text && <p className="coding-constraints">{q.constraints_text}</p>}
              <label className="wide-label">Language<select value={languages[q.id] || "python"} disabled={!active} onChange={e=>setLanguages(old=>({...old,[q.id]:e.target.value}))}><option value="python">Python</option><option value="cpp">C++</option><option value="java">Java</option><option value="javascript">JavaScript</option></select></label>
              <textarea className="code-editor" spellCheck="false" rows="10" disabled={!active} value={code[q.id] ?? q.starter_code?.[languages[q.id] || "python"] ?? ""} onChange={e=>setCode(old=>({...old,[q.id]:e.target.value}))} placeholder="Write your solution here…"/>
              <div className="code-actions"><button className="primary-button" disabled={!active || busy} onClick={()=>submitCode(q)}><Code2 size={14}/> Submit code</button>{submissions[q.id] && <span className="submission-state">{submissions[q.id].status}{submissions[q.id].result ? " · " + submissions[q.id].result.verdict + " · " + submissions[q.id].result.score + "%" : ""}</span>}</div>
            </article>)}
            {active && <button className="primary-button" disabled={busy || !canFinish} onClick={finish}>Finish assessment <CheckCircle2 size={15}/></button>}
            {!codingComplete && active && <p className="muted">Finish becomes available after each coding question has a completed evaluation result.</p>}
          </section>}
          {detail.status === "SUBMITTED" && detail.final_result && <div className="success-message">Final score: {detail.final_result.score}%</div>}
          {detail.status === "COMPLETED" && <div className="success-message">This assessment is complete.</div>}
        </>}
      </section>
    </div>
  </div>;
}

function EmployerAssessments() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [assessments, setAssessments] = useState([]);
  const [aptitude, setAptitude] = useState([]);
  const [coding, setCoding] = useState([]);
  const [applications, setApplications] = useState([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [selectedApplications, setSelectedApplications] = useState([]);
  const [selectedAptitude, setSelectedAptitude] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState([]);
  const [assessmentType, setAssessmentType] = useState("APTITUDE");
  const [duration, setDuration] = useState(45);
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [title, setTitle] = useState("Technical screening");
  const [questionForm, setQuestionForm] = useState({ category:"Reasoning", difficulty:"EASY", prompt:"", a:"", b:"", c:"", d:"", answer_key:"A", marks:1, negative_marks:0 });
  const [codingForm, setCodingForm] = useState({ title:"", slug:"", statement:"", difficulty:"EASY" });
  const [showAptitudeForm, setShowAptitudeForm] = useState(false);
  const [showCodingForm, setShowCodingForm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadJobs() {
    try {
      const result = await apiRequest("/jobs/mine");
      setJobs(result);
      if (!jobId && result.length) setJobId(result[0].id);
    } catch(e) { setError(e.message); }
  }
  async function loadResources() {
    if (!jobId) return;
    setError("");
    try {
      const [a, c, list, apps] = await Promise.all([
        apiRequest("/assessments/questions/aptitude"),
        apiRequest("/assessments/questions/coding"),
        apiRequest("/assessments/job/" + jobId),
        apiRequest("/jobs/" + jobId + "/applications"),
      ]);
      setAptitude(a); setCoding(c); setAssessments(list); setApplications(apps);
    } catch(e) { setError(e.message); }
  }
  useEffect(() => { loadJobs(); }, []);
  useEffect(() => { loadResources(); }, [jobId]);

  function toggleList(list, setList, id) {
    setList(old => old.includes(id) ? old.filter(value => value !== id) : [...old, id]);
  }
  async function createAptitude(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const options = [{id:"A",text:questionForm.a},{id:"B",text:questionForm.b},{id:"C",text:questionForm.c},{id:"D",text:questionForm.d}];
    try {
      const result = await apiRequest("/assessments/questions/aptitude", { method:"POST", body:JSON.stringify({
        category:questionForm.category, difficulty:questionForm.difficulty, prompt:questionForm.prompt,
        options, answer_key:questionForm.answer_key, marks:Number(questionForm.marks), negative_marks:Number(questionForm.negative_marks)
      })});
      setNotice("Question added to your company's question bank.");
      setQuestionForm({category:"Reasoning",difficulty:"EASY",prompt:"",a:"",b:"",c:"",d:"",answer_key:"A",marks:1,negative_marks:0});
      setShowAptitudeForm(false); await loadResources();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function createCoding(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const slug = codingForm.slug || codingForm.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
    try {
      await apiRequest("/assessments/questions/coding", { method:"POST", body:JSON.stringify({
        ...codingForm, slug, starter_code:{python:"",cpp:"",javascript:""}
      })});
      setNotice("Coding question added to your company's question bank.");
      setCodingForm({title:"",slug:"",statement:"",difficulty:"EASY"}); setShowCodingForm(false); await loadResources();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function createAssessment(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/assessments", { method:"POST", body:JSON.stringify({
        job_id:jobId, title, assessment_type:assessmentType, duration_minutes:Number(duration),
        max_attempts:Number(maxAttempts),
        aptitude_question_ids:assessmentType === "CODING" ? [] : selectedAptitude,
        coding_question_ids:assessmentType === "APTITUDE" ? [] : selectedCoding,
      })});
      setNotice("Assessment created. Next, select applicants and send invitations.");
      setAssessmentId(result.id); setSelectedApplications([]); setSelectedAptitude([]); setSelectedCoding([]);
      await loadResources();
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function inviteApplicants(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest("/assessments/" + assessmentId + "/invite", { method:"POST", body:JSON.stringify({application_ids:selectedApplications}) });
      setNotice("Invitations created: " + result.created.length + "; already invited: " + result.already_invited.length + ".");
      setSelectedApplications([]);
    } catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  const usableAptitude = assessmentType !== "CODING";
  const usableCoding = assessmentType !== "APTITUDE";
  return <div className="assessment-view">
    <div className="welcome-row"><div><p className="eyebrow">RECRUITMENT EVALUATION</p><h1>Assessment studio<span className="heading-period">.</span></h1><p className="muted">Create company-specific questions or use the platform question bank, then invite applicants to structured assessments.</p></div><span className="tiny-tag">EMPLOYER</span></div>
    <Alert error={error} notice={notice}/>
    <section className="panel assessment-builder">
      <div className="panel-heading"><div><h2>1. Choose a job</h2><p>Assessments are tied to a specific job opening.</p></div></div>
      <label className="wide-label">Job opening<select value={jobId} onChange={e=>{setJobId(e.target.value);setAssessmentId("");}}><option value="">Select a job</option>{jobs.map(job=><option key={job.id} value={job.id}>{job.title} · {job.status}</option>)}</select></label>
      {!jobs.length && <p className="muted">Create a job opening before building an assessment.</p>}
    </section>
    {jobId && <>
      <div className="assessment-tool-grid">
        <section className="panel"><div className="panel-heading"><div><h2>2. Question bank</h2><p>Platform defaults plus questions owned by your company.</p></div></div>
          <div className="question-bank-header"><b><ClipboardList size={15}/> Aptitude ({aptitude.length})</b><button className="secondary-button" onClick={()=>setShowAptitudeForm(!showAptitudeForm)}><Plus size={13}/> Add custom</button></div>
          {showAptitudeForm && <form className="assessment-form" onSubmit={createAptitude}><label>Category<input required value={questionForm.category} onChange={e=>setQuestionForm({...questionForm,category:e.target.value})}/></label><label>Difficulty<select value={questionForm.difficulty} onChange={e=>setQuestionForm({...questionForm,difficulty:e.target.value})}><option>EASY</option><option>MEDIUM</option><option>HARD</option></select></label><label>Question<textarea required minLength="5" rows="3" value={questionForm.prompt} onChange={e=>setQuestionForm({...questionForm,prompt:e.target.value})}/></label><div className="question-option-inputs">{["a","b","c","d"].map((key,index)=><label key={key}>Option {String.fromCharCode(65+index)}<input required value={questionForm[key]} onChange={e=>setQuestionForm({...questionForm,[key]:e.target.value})}/></label>)}</div><div className="form-grid"><label>Correct option<select value={questionForm.answer_key} onChange={e=>setQuestionForm({...questionForm,answer_key:e.target.value})}><option>A</option><option>B</option><option>C</option><option>D</option></select></label><label>Marks<input type="number" min="0.25" step="0.25" value={questionForm.marks} onChange={e=>setQuestionForm({...questionForm,marks:e.target.value})}/></label></div><button className="primary-button" disabled={busy}>Save question</button></form>}
          <div className="assessment-question-pick-list">{aptitude.map(q=><label key={q.id} className="question-pick"><input type="checkbox" checked={selectedAptitude.includes(q.id)} onChange={()=>toggleList(selectedAptitude,setSelectedAptitude,q.id)}/><span><b>{q.category} · {q.difficulty}</b><small>{q.prompt}</small></span><em>{q.scope}</em></label>)}</div>
          <div className="question-bank-header"><b><Code2 size={15}/> Coding ({coding.length})</b><button className="secondary-button" onClick={()=>setShowCodingForm(!showCodingForm)}><Plus size={13}/> Add custom</button></div>
          {showCodingForm && <form className="assessment-form" onSubmit={createCoding}><label>Question title<input required minLength="3" value={codingForm.title} onChange={e=>{const title=e.target.value;setCodingForm({...codingForm,title,slug:title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")})}}/></label><label>Slug<input required value={codingForm.slug} onChange={e=>setCodingForm({...codingForm,slug:e.target.value})}/></label><label>Difficulty<select value={codingForm.difficulty} onChange={e=>setCodingForm({...codingForm,difficulty:e.target.value})}><option>EASY</option><option>MEDIUM</option><option>HARD</option></select></label><label>Problem statement<textarea required minLength="10" rows="4" value={codingForm.statement} onChange={e=>setCodingForm({...codingForm,statement:e.target.value})}/></label><button className="primary-button" disabled={busy}>Save coding question</button></form>}
          <div className="assessment-question-pick-list">{coding.map(q=><label key={q.id} className="question-pick"><input type="checkbox" checked={selectedCoding.includes(q.id)} onChange={()=>toggleList(selectedCoding,setSelectedCoding,q.id)}/><span><b>{q.title} · {q.difficulty}</b><small>{q.statement}</small></span><em>{q.scope}</em></label>)}</div>
        </section>
        <section className="panel"><div className="panel-heading"><div><h2>3. Configure assessment</h2><p>Select the type, duration, and questions.</p></div></div>
          <form className="assessment-form" onSubmit={createAssessment}><label>Assessment title<input required minLength="3" value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Assessment type<select value={assessmentType} onChange={e=>setAssessmentType(e.target.value)}><option value="APTITUDE">Aptitude</option><option value="CODING">Coding</option><option value="MIXED">Aptitude + Coding</option></select></label><div className="form-grid"><label>Duration (minutes)<input type="number" min="5" max="240" value={duration} onChange={e=>setDuration(e.target.value)}/></label><label>Attempts allowed<select value={maxAttempts} onChange={e=>setMaxAttempts(e.target.value)}><option value="1">1 attempt</option><option value="2">2 attempts</option><option value="3">3 attempts</option><option value="5">5 attempts</option></select></label></div>
          <p className="muted">{usableAptitude ? selectedAptitude.length + " aptitude question(s)" : "Aptitude section not included"} · {usableCoding ? selectedCoding.length + " coding question(s)" : "Coding section not included"}</p>
          <button className="primary-button" disabled={busy || !jobId}>Create assessment <ArrowRight size={14}/></button></form>
          <div className="panel-heading assessment-subheading"><div><h2>Existing assessments</h2><p>Choose one to invite applicants.</p></div></div>
          {assessments.map(a=><button key={a.id} className={"assessment-invite " + (assessmentId===a.id?"selected":"")} onClick={()=>setAssessmentId(a.id)}><span className="assessment-invite-icon"><ClipboardList size={17}/></span><span className="assessment-invite-copy"><b>{a.title}</b><small>{a.assessment_type} · {a.question_count} questions · {a.duration_minutes} min</small></span><span className="job-status">{assessmentId===a.id?"SELECTED":"SELECT"}</span></button>)}
          {assessmentId && <form className="assessment-form" onSubmit={inviteApplicants}><div className="panel-heading"><div><h2>4. Invite applicants</h2><p>{applications.length} application(s) for this job.</p></div></div><div className="assessment-question-pick-list">{applications.map(app=><label key={app.application_id} className="question-pick"><input type="checkbox" checked={selectedApplications.includes(app.application_id)} onChange={()=>toggleList(selectedApplications,setSelectedApplications,app.application_id)}/><span><b>{app.full_name}</b><small>{app.email} · {app.status}</small></span><em>{app.match_score == null ? "NO MATCH" : Math.round(app.match_score)+"%"}</em></label>)}</div><button className="primary-button" disabled={busy || !selectedApplications.length}>Send invitations <Send size={14}/></button></form>}
        </section>
      </div>
    </>}
  </div>;
}

export default function AssessmentCenter({ user }) {
  return user?.role === "STUDENT" ? <StudentAssessments /> : user?.role === "COMPANY_HR" ? <EmployerAssessments /> :
    <div className="panel"><h2>Assessment workspace</h2><p className="muted">Assessment management is available to company members; assigned assessments are available to students.</p></div>;
}
