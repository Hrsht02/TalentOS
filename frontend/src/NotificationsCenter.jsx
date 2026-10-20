import { useEffect, useState } from "react";
import { Bell, CheckCheck, RefreshCw } from "lucide-react";
import { apiRequest } from "./api";

export default function NotificationsCenter() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true); setError("");
    try { setItems(await apiRequest("/notifications?limit=100")); }
    catch (e) { setError(e.message || "Could not load notifications."); }
    finally { setBusy(false); }
  }

  async function markRead(item) {
    try {
      const updated = await apiRequest("/notifications/" + item.id + "/read", { method: "POST" });
      setItems(old => old.map(row => row.id === updated.id ? updated : row));
    } catch (e) { setError(e.message || "Could not mark notification as read."); }
  }

  async function markAllRead() {
    const unread = items.filter(item => !item.read_at);
    for (const item of unread) await markRead(item);
  }

  useEffect(() => { load(); }, []);
  return <div className="jobs-view">
    <div className="welcome-row"><div><p className="eyebrow">ACTIVITY CENTER</p><h1>Notifications<span className="heading-period">.</span></h1><p className="muted">Assessment deadlines, interview reminders and recruitment workflow updates.</p></div><div className="employer-job-actions"><button className="secondary-button" onClick={load} disabled={busy}><RefreshCw size={14}/> Refresh</button><button className="primary-button" onClick={markAllRead} disabled={busy || !items.some(item => !item.read_at)}><CheckCheck size={14}/> Mark all read</button></div></div>
    {error && <div className="error-message jobs-message">{error}</div>}
    {busy && !items.length && <section className="panel"><p>Loading notifications…</p></section>}
    {!busy && !items.length && !error && <section className="panel"><div className="empty-activity"><span className="empty-icon"><Bell size={22}/></span><b>You're all caught up</b><p>New workflow reminders will appear here.</p></div></section>}
    {items.map(item => <section className="panel" key={item.id}><div className="step-row"><span className="step-number"><Bell size={16}/></span><div style={{flex:1}}><b>{item.title}</b><p>{item.body}</p><small>{item.kind.replaceAll("_"," ")} · {new Date(item.created_at).toLocaleString()}</small></div>{!item.read_at && <button className="secondary-button" onClick={()=>markRead(item)}>Mark read</button>}</div></section>)}
  </div>;
}
