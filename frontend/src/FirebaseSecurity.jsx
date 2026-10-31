import React, {useState, useEffect} from 'react';
import {auth} from './firebase.js';
import {
  createUserWithEmailAndPassword,signInWithEmailAndPassword,GoogleAuthProvider,
  signInWithPopup,signOut,sendEmailVerification,updateProfile,reload
} from 'firebase/auth';
import {ShieldCheck,UserRound,LogIn,LogOut,MailCheck,RefreshCw} from 'lucide-react';

export default function FirebaseSecurity({session, authStatus, authError}) {
  const [mode,setMode]=useState('login');
  const [email,setEmail]=useState('');
  const [password,setPassword]=useState('');
  const [name,setName]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [user,setUser]=useState(auth.currentUser);
  const [lastSent,setLastSent]=useState(0);
  useEffect(()=>auth.onAuthStateChanged(next=>setUser(next)),[]);

  async function act(e){
    e.preventDefault();setBusy(true);setMessage('');
    try {
      if(mode==='register') {
        const result=await createUserWithEmailAndPassword(auth,email,password);
        if(name.trim())await updateProfile(result.user,{displayName:name.trim()});
        await sendEmailVerification(result.user);
        setLastSent(Date.now());
        setMessage('Account created and verification email requested. Open the link in your inbox, then select I verified my email.');
      } else {
        await signInWithEmailAndPassword(auth,email,password);
        setMessage('Firebase sign-in succeeded. Checking email verification and backend access…');
      }
    }catch(err){setMessage(`Firebase: ${err.code || err.message}`)}finally{setBusy(false)}
  }
  async function google(){
    setBusy(true);setMessage('');
    try {await signInWithPopup(auth,new GoogleAuthProvider());setMessage('Google sign-in succeeded. Checking backend access…');}
    catch(err){setMessage(`Google sign-in: ${err.code || err.message}`)}finally{setBusy(false)}
  }
  async function resend(){
    if(!auth.currentUser){setMessage('Please sign in first.');return;}
    if(Date.now()-lastSent<60000){setMessage('A verification email was requested recently. Check your inbox or try again after one minute.');return;}
    setBusy(true);setMessage('');
    try {
      await sendEmailVerification(auth.currentUser);
      setLastSent(Date.now());
      setMessage('Verification email requested. Check your inbox and spam folder.');
    }catch(err){setMessage(`Verification email: ${err.code || err.message}`)}finally{setBusy(false)}
  }
  async function refreshVerification(){
    if(!auth.currentUser){setMessage('Please sign in first.');return;}
    setBusy(true);setMessage('');
    try {
      await reload(auth.currentUser);
      await auth.currentUser.getIdToken(true);
      setUser(auth.currentUser);
      setMessage(auth.currentUser.emailVerified
        ? 'Email verified! A fresh token was issued. Your backend role should update shortly.'
        : 'Firebase still shows this email as unverified. Open the verification link, then retry.');
    }catch(err){setMessage(`Refresh failed: ${err.code || err.message}`)}finally{setBusy(false)}
  }
  async function logout(){setMessage('');try{await signOut(auth)}catch(err){setMessage(err.message)}}
  return <section className="panel advanced-panel">
    <h3><ShieldCheck size={20}/> Firebase identity &amp; access</h3>
    <p className="fine">Firebase manages credentials. FastAPI verifies tokens. Newly verified accounts receive Viewer permissions by default; only a trusted server command can grant higher roles.</p>
    {session?.user ? <div className="auth-profile"><UserRound size={24}/><div><b>{session.user.display_name}</b><p>{session.user.email} · {session.user.role.toUpperCase()}</p><small>Backend identity verified</small></div><button className="outline-btn" onClick={logout}><LogOut size={16}/> Log out</button></div>
    : <>
      {user ? <div className="auth-profile"><UserRound size={24}/><div><b>{user.displayName || user.email}</b><p>Firebase signed in · {user.emailVerified ? 'Email verified' : 'Email not verified'}</p><small>{authStatus==='checking'?'Checking backend identity…':authStatus==='error'?'Backend authorization requires attention':'Awaiting backend confirmation'}</small></div><button className="outline-btn" onClick={logout}><LogOut size={16}/> Log out</button></div>
      : <><div className="filter-pills"><button type="button" className={mode==='login'?'selected':''} onClick={()=>setMode('login')}>Sign in</button><button type="button" className={mode==='register'?'selected':''} onClick={()=>setMode('register')}>Register</button></div>
        <form className="payment-form auth-form" onSubmit={act}>
          {mode==='register'&&<label>Display name<input value={name} onChange={e=>setName(e.target.value)} required/></label>}
          <label>Email<input type="email" required autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)}/></label>
          <label>Password<input type="password" required minLength="6" autoComplete={mode==='register'?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)}/></label>
          <button className="primary" disabled={busy}><LogIn size={16}/>{busy?'Working…':mode==='register'?'Register':'Sign in'}</button>
        </form><button type="button" className="outline-btn" disabled={busy} onClick={google}>Continue with Google</button></>}
      {user&&!user.emailVerified&&<div className="verification-actions">
        <p className="fine">Verify your email to unlock backend access. Check Inbox and Spam for the Firebase message.</p>
        <button className="outline-btn" type="button" disabled={busy} onClick={resend}><MailCheck size={16}/> Resend verification email</button>
        <button className="outline-btn" type="button" disabled={busy} onClick={refreshVerification}><RefreshCw size={16}/> I verified my email</button>
      </div>}
      {user&&user.emailVerified&&!session&&<button className="outline-btn" type="button" disabled={busy} onClick={refreshVerification}><RefreshCw size={16}/> Retry backend verification</button>}
    </>}
    {message&&<p role="status" className="feedback">{message}</p>}
    {authError&&<p role="alert" className="feedback">Backend: {authError}</p>}
  </section>;
}
