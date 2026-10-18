import React from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { QuickTest } from "./pages/QuickTest";
import { Login, Dashboard, NewReview } from "./pages/Dashboard";
import { Policies } from "./pages/Policies";
import { ReviewPage } from "./pages/ReviewPage";
import { PublicWorkspace } from "./pages/PublicWorkspace";
import { operatorSignedIn, request } from "./api";
import { Icon } from "./components/Icon";
import "./studio.css";
function Guard({ children }: { children: React.ReactNode }) {
  return operatorSignedIn() ? (
    children
  ) : (
    <Navigate to="/operator/login" replace />
  );
}
function Shell() {
  const location = useLocation(),
    navigate = useNavigate();
  React.useEffect(() => {
    sessionStorage.removeItem("dubguard-reviewer");
    document
      .querySelector<HTMLDetailsElement>(".mobile-navigation")
      ?.removeAttribute("open");
  }, [location.pathname, location.search]);
  return (
    <div className="app-layout">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="app-sidebar" aria-label="Workspace navigation">
        <NavLink to="/test" className="brand">
          <span aria-hidden="true" className="brand-mark">
            <Icon name="wave" size={24} />
          </span>
          <span>
            DubGuard<small>EVIDENCE STUDIO</small>
          </span>
        </NavLink>
        <span className="sidebar-label">WORKSPACE</span>
        <nav className="sidebar-nav" aria-label="Workspace">
          <NavLink to="/test">
            <Icon name="wave" />
            Try a Sample
          </NavLink>
          <NavLink to="/workspace">
            <Icon name="plus" />
            Create a Review
          </NavLink>
          {operatorSignedIn() && (
            <>
              <span className="sidebar-label">PRIVATE OPERATOR</span>
              <a href="/review#workspace-overview">
                <Icon name="grid" />
                Overview
              </a>
              <NavLink to="/review" end>
                <Icon name="queue" />
                Review queue
              </NavLink>
              <NavLink to="/review/new">
                <Icon name="plus" />
                New recording
              </NavLink>
              <NavLink to="/policies">
                <Icon name="script" />
                Policies
              </NavLink>
              <a href="/review?view=history">
                <Icon name="queue" />
                Review history
              </a>
            </>
          )}
        </nav>
        <div className="sidebar-principle">
          <Icon name="shield" size={26} />
          <strong>Evidence before approval.</strong>
          <p>
            Your demo stays isolated.
            <br />
            Release sign-off stays protected.
          </p>
        </div>
        <div className="sidebar-bottom">
          <span className="sidebar-monogram">DG</span>
          <div>
            DubGuard workspace<small>Narration integrity</small>
          </div>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <div className="workspace-breadcrumb">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>
              {location.pathname === "/test"
                ? "Quick Test"
                : location.pathname === "/workspace"
                  ? "Create a Review"
                  : location.pathname === "/policies"
                    ? "Scripts & policies"
                    : location.pathname === "/login" ||
                        location.pathname === "/operator/login"
                      ? "Reviewer access"
                      : location.pathname === "/review"
                        ? "Review queue"
                        : "Evidence review"}
            </strong>
          </div>
          <nav aria-label="Main navigation">
            <NavLink to="/test">Try a Sample</NavLink>
            <NavLink to="/workspace">Create a Review</NavLink>
            {operatorSignedIn() ? (
              <button
                className="text-button"
                onClick={async () => {
                  sessionStorage.removeItem("dubguard-operator");
                  await request(
                    "/operator/session",
                    { method: "DELETE", keepalive: true },
                    "",
                  );
                  navigate("/test");
                }}
              >
                Sign out
              </button>
            ) : (
              <span className="nav-note">
                <Icon name="shield" size={14} /> Temporary & isolated
              </span>
            )}
          </nav>
        </header>
        <details className="mobile-navigation">
          <summary>
            <Icon name="menu" /> DubGuard <span>Workspace menu</span>
          </summary>
          <nav aria-label="Mobile workspace">
            <NavLink to="/test">Try a Sample</NavLink>
            <NavLink to="/workspace">Create a Review</NavLink>
          </nav>
        </details>
        <main id="main" key={location.pathname}>
          <Routes>
            <Route path="/" element={<Navigate to="/test" replace />} />
            <Route path="/test" element={<QuickTest />} />
            <Route path="/workspace" element={<PublicWorkspace />} />
            <Route
              path="/operator"
              element={
                <Guard>
                  <Dashboard />
                </Guard>
              }
            />
            <Route path="/operator/login" element={<Login />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/review"
              element={
                <Guard>
                  <Dashboard />
                </Guard>
              }
            />
            <Route
              path="/review/new"
              element={
                <Guard>
                  <NewReview />
                </Guard>
              }
            />
            <Route
              path="/review/:id"
              element={
                <Guard>
                  <ReviewPage />
                </Guard>
              }
            />
            <Route
              path="/policies"
              element={
                <Guard>
                  <Policies />
                </Guard>
              }
            />
            <Route
              path="*"
              element={
                <section className="panel">
                  <h1>Page not found</h1>
                  <NavLink to="/test">Open Quick Test</NavLink>
                </section>
              }
            />
          </Routes>
        </main>
        <footer>
          DubGuard · A review aid, never automatic safety certification or
          release approval.
        </footer>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </React.StrictMode>,
);
