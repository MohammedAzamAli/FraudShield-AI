
import React, { useEffect, useRef, useState } from "react";

import {
  onIdTokenChanged,
  signOut,
} from "firebase/auth";

import {
  ShieldCheck,
  LockKeyhole,
  Activity,
  ShieldAlert,
  Fingerprint,
  LogOut,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";

import { auth } from "./firebase.js";
import FirebaseSecurity from "./FirebaseSecurity.jsx";
import App from "./App.jsx";


const API =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

const ALLOWED_ROLES = new Set([
  "admin",
  "analyst",
]);


export default function AuthGate() {
  const [authStatus, setAuthStatus] = useState("checking");
  const [authError, setAuthError] = useState("");
  const [session, setSession] = useState(null);

  const [retryCount, setRetryCount] = useState(0);

  // Prevent an older asynchronous response from
  // restoring access after sign-out or token changes.
  const checkVersion = useRef(0);


  useEffect(() => {
    let mounted = true;

    const unsubscribe = onIdTokenChanged(
      auth,
      async (firebaseUser) => {
        const version = ++checkVersion.current;

        setSession(null);
        setAuthError("");

        if (!firebaseUser) {
          setAuthStatus("signed-out");
          return;
        }

        setAuthStatus("checking");

        try {
          // Firebase supplies the identity token.
          const token = await firebaseUser.getIdToken();

          const response = await fetch(
            API + "/api/auth/me",
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
              cache: "no-store",
            }
          );

          if (!mounted || version !== checkVersion.current) {
            return;
          }

          if (!response.ok) {
            let detail = "Backend identity verification failed.";

            try {
              const data = await response.json();

              if (typeof data.detail === "string") {
                detail = data.detail;
              }
            } catch {
              // Keep the generic error.
            }

            setAuthError(detail);
            setAuthStatus("error");
            return;
          }

          const profile = await response.json();

          if (!mounted || version !== checkVersion.current) {
            return;
          }

          const role = String(
            profile.role || ""
          ).toLowerCase();

          // Viewer accounts cannot enter the
          // investigator workspace.
          if (!ALLOWED_ROLES.has(role)) {
            setAuthError(
              "Your account is authenticated but does not " +
              "have access to the investigator workspace. " +
              "Contact an administrator for an authorized role."
            );

            setAuthStatus("denied");
            return;
          }

          // Double-check that the session still belongs
          // to the same signed-in Firebase user.
          if (auth.currentUser?.uid !== firebaseUser.uid) {
            setAuthStatus("signed-out");
            return;
          }

          setSession({
            access_token: token,
            user: profile,
          });

          setAuthStatus("verified");

        } catch {
          if (!mounted || version !== checkVersion.current) {
            return;
          }

          setAuthError(
            "Unable to verify your identity with FastAPI. " +
            "Check that the backend is running."
          );

          setAuthStatus("error");
        }
      }
    );

    return () => {
      mounted = false;
      ++checkVersion.current;
      unsubscribe();
    };

  }, [retryCount]);


  async function retryVerification() {
    setAuthError("");
    setAuthStatus("checking");

    try {
      if (auth.currentUser) {
        await auth.currentUser.reload();
        await auth.currentUser.getIdToken(true);
      }

      // Re-register the listener if Firebase does
      // not emit a new token event.
      setRetryCount(value => value + 1);

    } catch {
      setAuthError(
        "Unable to refresh your session. " +
        "Try signing out and signing in again."
      );

      setAuthStatus("error");
    }
  }


  async function logout() {
    ++checkVersion.current;
    setSession(null);
    setAuthStatus("signed-out");

    try {
      await signOut(auth);
    } catch {
      setAuthError(
        "Unable to complete Firebase sign-out. " +
        "Please retry."
      );

      setAuthStatus("error");
    }
  }


  // ----------------------------------------------------
  // AUTHORIZED WORKSPACE
  // ----------------------------------------------------

  if (authStatus === "verified" && session) {
    return <App key={session.user.id} />;
  }


  // ----------------------------------------------------
  // SESSION VERIFICATION SCREEN
  // ----------------------------------------------------

  if (authStatus === "checking") {
    return (
      <main className="fs-auth-shell">
        <div
          className="fs-auth-loading"
          role="status"
          aria-live="polite"
        >
          <div className="fs-auth-logo">
            <ShieldCheck size={30} />
          </div>

          <h1>FraudShield AI</h1>

          <p>Verifying your secure session...</p>

          <RefreshCw
            className="fs-auth-spinner"
            size={25}
          />
        </div>
      </main>
    );
  }


  // ----------------------------------------------------
  // LOGIN-FIRST INTERFACE
  // ----------------------------------------------------

  return (
    <main className="fs-auth-shell">

      <div className="fs-auth-background" />

      <div className="fs-auth-layout">

        {/* LEFT INFORMATION PANEL */}
        <section className="fs-auth-showcase">

          <div className="fs-auth-brand">
            <div className="fs-auth-logo">
              <ShieldCheck size={30} />
            </div>

            <div>
              <h1>
                FraudShield<span>AI</span>
              </h1>

              <p>FINANCIAL SECURITY PLATFORM</p>
            </div>
          </div>


          <div className="fs-auth-hero">
            <div className="fs-auth-eyebrow">
              <span className="fs-auth-dot" />
              SECURE FRAUD INTELLIGENCE
            </div>

            <h2>
              Detect risk.
              <br />
              Investigate smarter.
              <br />
              <span>Protect with intelligence.</span>
            </h2>

            <p>
              A controlled academic platform for
              UPI fraud risk analysis, AI-assisted
              investigations, transaction monitoring
              and financial security research.
            </p>
          </div>


          <div className="fs-auth-features">

            <div className="fs-auth-feature">
              <div className="fs-auth-feature-icon">
                <Activity size={20} />
              </div>

              <div>
                <strong>Fraud Intelligence</strong>
                <p>
                  Transaction risk monitoring and
                  research analytics.
                </p>
              </div>
            </div>


            <div className="fs-auth-feature">
              <div className="fs-auth-feature-icon">
                <Fingerprint size={20} />
              </div>

              <div>
                <strong>Verified Access</strong>
                <p>
                  Firebase identity verification with
                  role-based investigator permissions.
                </p>
              </div>
            </div>


            <div className="fs-auth-feature">
              <div className="fs-auth-feature-icon">
                <ShieldAlert size={20} />
              </div>

              <div>
                <strong>AI-Assisted Investigations</strong>
                <p>
                  Evidence-aware analysis with
                  human review and audit history.
                </p>
              </div>
            </div>

          </div>


          <p className="fs-auth-footer">
            Academic research sandbox · Synthetic
            transactions · No real payment processing
          </p>

        </section>


        {/* RIGHT LOGIN PANEL */}
        <section className="fs-auth-form-side">

          <div className="fs-auth-card">

            <div className="fs-auth-card-intro">
              <div className="fs-auth-lock">
                <LockKeyhole size={22} />
              </div>

              <h2>Secure Workspace</h2>

              <p>
                Sign in with your authorized Firebase
                account to access FraudShield AI.
              </p>
            </div>


            {authStatus === "denied" && (
              <div
                className="fs-auth-alert"
                role="alert"
              >
                <ShieldAlert size={18} />
                <span>{authError}</span>
              </div>
            )}


            {authStatus === "error" && (
              <div
                className="fs-auth-alert"
                role="alert"
              >
                <ShieldAlert size={18} />
                <span>{authError}</span>
              </div>
            )}


            {/* REUSE EXISTING FIREBASE LOGIN */}
            <div className="fs-auth-firebase">
              <FirebaseSecurity
                session={null}
                authStatus={authStatus}
                authError={null}
              />
            </div>


            {(authStatus === "error" ||
              authStatus === "denied") && (
              <div className="fs-auth-actions">
                <button
                  type="button"
                  onClick={retryVerification}
                  className="fs-auth-action"
                >
                  <RefreshCw size={16} />
                  Retry verification
                </button>

                <button
                  type="button"
                  onClick={logout}
                  className="fs-auth-action"
                >
                  <LogOut size={16} />
                  Sign out
                </button>
              </div>
            )}


            <div className="fs-auth-trust">
              <CheckCircle2 size={15} />
              <span>
                Firebase Authentication ·
                FastAPI identity verification
              </span>
            </div>

          </div>

        </section>

      </div>

    </main>
  );
}
