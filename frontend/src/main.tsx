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
import { token } from "./api";
import "./style.css";
function Guard({ children }: { children: React.ReactNode }) {
  return token() ? children : <Navigate to="/login" replace />;
}
function Shell() {
  const location = useLocation(),
    navigate = useNavigate();
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="app-header">
        <NavLink to="/test" className="brand">
          <span aria-hidden="true" className="brand-mark">
            D
          </span>
          <span>
            DubGuard<small>NARRATION INTEGRITY</small>
          </span>
        </NavLink>
        <nav aria-label="Main navigation">
          <NavLink to="/test">Quick Test</NavLink>
          <NavLink to="/review">Full Review</NavLink>
          {token() ? (
            <button
              className="text-button"
              onClick={() => {
                sessionStorage.removeItem("dubguard-reviewer");
                navigate("/login");
              }}
            >
              Sign out
            </button>
          ) : (
            <NavLink to="/login">Reviewer sign in</NavLink>
          )}
        </nav>
      </header>
      <main id="main" key={location.pathname}>
        <Routes>
          <Route path="/" element={<Navigate to="/test" replace />} />
          <Route path="/test" element={<QuickTest />} />
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
        DubGuard · A review aid, never automatic safety certification or release
        approval.
      </footer>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </React.StrictMode>,
);
