import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const TOUR_STORAGE_KEY = "pricewise_tour_seen_v1";

const TOUR_STEPS = [
  {
    path: "/",
    title: "Dashboard",
    description: "This is the home page. You can quickly see main numbers and latest live events.",
  },
  {
    path: "/products",
    title: "Products",
    description: "Manage products here. Add, edit, delete, and check prices, stock, and competitor comparison.",
  },
  {
    path: "/decisions",
    title: "Decisions",
    description: "See what decision was taken, why it was taken, and whether it was executed.",
  },
  {
    path: "/alerts",
    title: "Alerts",
    description: "Find low-stock and out-of-stock items. You can update stock from this page.",
  },
  {
    path: "/insights/margin",
    title: "Runtime & AI",
    description:
      "This section helps you watch margin health. Runtime and AI run in short sessions to control API usage.",
  },
];

function OnboardingTour() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const seen = window.localStorage.getItem(TOUR_STORAGE_KEY);
    if (!seen) {
      setIsOpen(true);
      setStep(0);
    }
  }, []);

  const activeStep = useMemo(() => TOUR_STEPS[step], [step]);
  const isLast = step === TOUR_STEPS.length - 1;

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    navigate(TOUR_STEPS[step].path, { replace: true });
  }, [isOpen, navigate, step]);

  function closeTour() {
    window.localStorage.setItem(TOUR_STORAGE_KEY, "1");
    setIsOpen(false);
  }

  function nextStep() {
    if (isLast) {
      closeTour();
      navigate("/", { replace: true });
      return;
    }
    const nextIndex = Math.min(step + 1, TOUR_STEPS.length - 1);
    setStep(nextIndex);
  }

  function previousStep() {
    const previousIndex = Math.max(step - 1, 0);
    setStep(previousIndex);
  }

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/75 px-4">
      <div className="panel w-full max-w-xl p-6">
        <p className="label">Welcome Tour</p>
        <h3 className="mt-1 text-xl font-semibold text-slate-50">{activeStep.title}</h3>
        <p className="mt-3 text-sm leading-6 text-slate-200">{activeStep.description}</p>

        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between text-xs text-muted">
            <span>
              Step {step + 1} of {TOUR_STEPS.length}
            </span>
            <span>{Math.round(((step + 1) / TOUR_STEPS.length) * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-900/70">
            <span
              className="block h-full rounded-full bg-accent transition-all duration-300"
              style={{ width: `${((step + 1) / TOUR_STEPS.length) * 100}%` }}
            />
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between gap-2">
          <button
            type="button"
            className="rounded-lg border border-line/70 px-3 py-2 text-sm text-muted hover:text-slate-100"
            onClick={closeTour}
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-lg border border-line/70 px-3 py-2 text-sm text-slate-100 disabled:opacity-40"
              onClick={previousStep}
              disabled={step === 0}
            >
              Back
            </button>
            <button
              type="button"
              className="rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-slate-100"
              onClick={nextStep}
            >
              {isLast ? "Start using app" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingTour;
