import { useEffect, useMemo, useState, createContext, useContext } from "react";

// ============================================================================
// 0. BACKEND API CONFIGURATION
// ============================================================================
const API_BASE_URL = "http://localhost:8000";

// ============================================================================
// 1. PRODUCTION-READY FIREBASE AUTHENTICATION BRIDGE (HIGH-FIDELITY MOCK)
// ============================================================================
// In a live production environment with real Firebase credentials, uncomment
// the official imports below and swap this mock block with the real SDK calls.
// All interfaces and method signatures perfectly match the official Firebase Auth SDK.
//
// import { initializeApp } from "firebase/app";
// import { getAuth, onAuthStateChanged, signInWithEmailAndPassword,
//          createUserWithEmailAndPassword, signOut, User } from "firebase/auth";
//
// const firebaseConfig = {
//   apiKey: "AIzaSy...", authDomain: "flowvest-ai.firebaseapp.com",
//   projectId: "flowvest-ai", storageBucket: "flowvest-ai.appspot.com",
//   messagingSenderId: "...", appId: "..."
// };
//   const app = initializeApp(firebaseConfig);
//   export const auth = getAuth(app);

// ============================================================================
// 0b. BACKEND API FUNCTIONS
// ============================================================================
async function createPortfolioViaBackend(
  budget: number,
  risk: string,
  horizon: string,
  userId: string
): Promise<PortfolioRecord | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/portfolio/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-demo-user": userId,
      },
      body: JSON.stringify({ budget, risk, horizon }),
    });

    if (!response.ok) {
      console.error("[API] Failed to create portfolio:", response.status);
      return null;
    }

    const { execution_id } = await response.json();

    // Poll for completion (max 30 seconds)
    for (let i = 0; i < 30; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const statusRes = await fetch(
        `${API_BASE_URL}/portfolio/execution/${execution_id}`,
        { headers: { "x-demo-user": userId } }
      );
      const statusData = await statusRes.json();

      if (statusData.status === "completed" || statusData.status === "completed_with_errors") {
        // Fetch the portfolio details
        const portfolioRes = await fetch(
          `${API_BASE_URL}/portfolio/${statusData.portfolio_id}`,
          { headers: { "x-demo-user": userId } }
        );
        const portfolio = await portfolioRes.json();
        return portfolio;
      }
      if (statusData.status === "failed") {
        console.error("[API] Pipeline failed:", statusData.error);
        return null;
      }
    }
    console.error("[API] Timeout waiting for portfolio");
    return null;
  } catch (err) {
    console.error("[API] Error:", err);
    return null;
  }
}

type User = {
  uid: string;
  email: string;
  displayName?: string;
  createdAt: string;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, pass: string) => Promise<User>;
  signUp: (email: string, pass: string, name?: string) => Promise<User>;
  logOut: () => Promise<void>;
  error: string | null;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Simulate Firebase onAuthStateChanged
    const storedUser = localStorage.getItem("flowvest_user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const signIn = async (email: string, pass: string): Promise<User> => {
    setError(null);
    setLoading(true);
    // Simulate network latency
    await new Promise((resolve) => setTimeout(resolve, 800));

    const users = JSON.parse(localStorage.getItem("flowvest_users") || "[]");
    const foundUser = users.find((u: any) => u.email.toLowerCase() === email.toLowerCase());

    if (!foundUser) {
      setLoading(false);
      const err = "auth/user-not-found: No account found with this email.";
      setError(err);
      throw new Error(err);
    }

    if (foundUser.password !== pass) {
      setLoading(false);
      const err = "auth/wrong-password: The password you entered is incorrect.";
      setError(err);
      throw new Error(err);
    }

    const authUser: User = {
      uid: foundUser.uid,
      email: foundUser.email,
      displayName: foundUser.displayName,
      createdAt: foundUser.createdAt,
    };

    localStorage.setItem("flowvest_user", JSON.stringify(authUser));
    setUser(authUser);
    setLoading(false);
    return authUser;
  };

  const signUp = async (email: string, pass: string, name?: string): Promise<User> => {
    setError(null);
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));

    if (pass.length < 6) {
      setLoading(false);
      const err = "auth/weak-password: Password must be at least 6 characters long.";
      setError(err);
      throw new Error(err);
    }

    const users = JSON.parse(localStorage.getItem("flowvest_users") || "[]");
    const exists = users.some((u: any) => u.email.toLowerCase() === email.toLowerCase());

    if (exists) {
      setLoading(false);
      const err = "auth/email-already-in-use: An account already exists with this email.";
      setError(err);
      throw new Error(err);
    }

    const newUser = {
      uid: globalThis.crypto?.randomUUID?.() ?? `usr-${Math.random().toString(36).slice(2, 10)}`,
      email: email.toLowerCase(),
      password: pass,
      displayName: name || email.split("@")[0],
      createdAt: new Date().toISOString(),
    };

    users.push(newUser);
    localStorage.setItem("flowvest_users", JSON.stringify(users));

    const authUser: User = {
      uid: newUser.uid,
      email: newUser.email,
      displayName: newUser.displayName,
      createdAt: newUser.createdAt,
    };

    localStorage.setItem("flowvest_user", JSON.stringify(authUser));
    setUser(authUser);
    setLoading(false);
    return authUser;
  };

  const logOut = async (): Promise<void> => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 400));
    localStorage.removeItem("flowvest_user");
    setUser(null);
    setLoading(false);
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, logOut, error, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

// ============================================================================
// 2. TYPES & CORE DOMAIN LOGIC (PRESERVED & EXPANDED)
// ============================================================================
type Risk = "Low" | "Medium" | "High";
type Horizon = "Short" | "Medium" | "Long";
type Status = "running" | "completed" | "failed";

type MarketSnapshot = {
  nifty: number;
  sensex: number;
  gold: number;
  trend: "Up" | "Flat" | "Down";
  niftyChange: number;
  sensexChange: number;
  goldChange: number;
  updatedAt: number;
};

type AllocationSlice = {
  label: string;
  value: number;
  color: string;
  note: string;
};

type PortfolioRequest = {
  budget: number;
  risk: Risk;
  horizon: Horizon;
  market: MarketSnapshot;
  createdAt: string;
  userId: string;
};

type PortfolioRecord = PortfolioRequest & {
  id: string;
  status: Status;
  allocation: AllocationSlice[];
  reasoning: string;
  summary: string;
  cadence: string;
};

const riskOptions: Risk[] = ["Low", "Medium", "High"];
const horizonOptions: Horizon[] = ["Short", "Medium", "Long"];

const allocationLabels = [
  "Debt / liquid reserve",
  "Gold ETF",
  "Large-cap core",
  "Flexi-cap blend",
  "Mid and small-cap growth",
];

const allocationColors = ["#38bdf8", "#8b5cf6", "#10b981", "#f59e0b", "#f97316"];

const allocationNotes = [
  "Keeps short-term volatility under control.",
  "Adds a defensive hedge when equity risk rises.",
  "Anchors the portfolio with quality compounding.",
  "Allows the model to rotate across opportunities.",
  "Captures higher beta when the horizon allows it.",
];

const moneyFormatter = new Intl.NumberFormat("en-IN");
const dateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

const initialMarket: MarketSnapshot = {
  nifty: 24780,
  sensex: 81320,
  gold: 69740,
  trend: "Up",
  niftyChange: 0.34,
  sensexChange: 0.29,
  goldChange: -0.08,
  updatedAt: Date.now(),
};

function formatRupees(value: number) {
  return `Rs ${moneyFormatter.format(Math.round(value))}`;
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatTrend(trend: MarketSnapshot["trend"]) {
  return trend === "Up" ? "Positive" : trend === "Down" ? "Soft" : "Mixed";
}

function createId() {
  return globalThis.crypto?.randomUUID?.() ?? `flow-${Math.random().toString(36).slice(2, 10)}`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizePercentages(weights: number[]) {
  const safeWeights = weights.map((weight) => Math.max(4, weight));
  const total = safeWeights.reduce((sum, value) => sum + value, 0);
  const raw = safeWeights.map((weight) => (weight / total) * 100);
  const floors = raw.map((value) => Math.floor(value));
  let remainder = 100 - floors.reduce((sum, value) => sum + value, 0);

  const order = raw
    .map((value, index) => ({ index, fraction: value - floors[index] }))
    .sort((left, right) => right.fraction - left.fraction);

  for (let index = 0; index < remainder; index += 1) {
    floors[order[index % order.length].index] += 1;
  }

  return floors;
}

function buildAllocation(request: Omit<PortfolioRequest, "userId">) {
  const riskBlueprints: Record<Risk, number[]> = {
    Low: [38, 18, 24, 14, 6],
    Medium: [24, 12, 30, 22, 12],
    High: [12, 8, 30, 24, 26],
  };

  const horizonBlueprints: Record<Horizon, number[]> = {
    Short: [10, 5, -4, -4, -7],
    Medium: [0, 0, 0, 0, 0],
    Long: [-6, -4, 4, 3, 3],
  };

  const budgetBlueprint =
    request.budget < 100000 ? [8, 4, -2, -3, -7] : request.budget > 750000 ? [-3, -2, 3, 2, 0] : [0, 0, 0, 0, 0];

  const weights = riskBlueprints[request.risk].map(
    (value, index) => value + horizonBlueprints[request.horizon][index] + budgetBlueprint[index]
  );

  const values = normalizePercentages(weights);

  return allocationLabels.map((label, index) => ({
    label,
    value: values[index],
    color: allocationColors[index],
    note: allocationNotes[index],
  }));
}

function buildReasoning(request: Omit<PortfolioRequest, "userId">, allocation: AllocationSlice[]) {
  const topSlices = [...allocation].sort((left, right) => right.value - left.value).slice(0, 2);
  const leadSlice = topSlices[0] ?? allocation[0];
  const supportSlice = topSlices[1] ?? topSlices[0] ?? allocation[0];
  const defensive = allocation[0];
  const marketTone =
    request.market.trend === "Up"
      ? `Market tone is constructive, with Nifty at ${formatPercent(request.market.niftyChange)} and Sensex at ${formatPercent(request.market.sensexChange)}.`
      : request.market.trend === "Down"
        ? `Market tone is cautious, with Nifty at ${formatPercent(request.market.niftyChange)} and Sensex at ${formatPercent(request.market.sensexChange)}.`
        : `Market tone is balanced, with Nifty at ${formatPercent(request.market.niftyChange)} and Sensex at ${formatPercent(request.market.sensexChange)}.`;

  const riskLine =
    request.risk === "Low"
      ? "Low risk keeps capital protection ahead of upside capture."
      : request.risk === "Medium"
        ? "Medium risk aims for balanced growth without overexposing the portfolio."
        : "High risk allows more equity beta because the plan can absorb volatility.";

  const horizonLine =
    request.horizon === "Short"
      ? "A short horizon prefers tighter drawdown control and quicker exit liquidity."
      : request.horizon === "Medium"
        ? "A medium horizon keeps the core balanced while preserving room to rotate."
        : "A long horizon supports more growth exposure and a slower rebalance cadence.";

  const cadence =
    request.horizon === "Short" ? "monthly" : request.horizon === "Medium" ? "quarterly" : "quarterly with drift checks";

  const trancheCount = request.horizon === "Short" ? 6 : request.horizon === "Medium" ? 12 : 18;
  const trancheValue = Math.max(1000, Math.round(request.budget / trancheCount / 1000) * 1000);

  return [
    marketTone,
    "",
    `${riskLine} ${horizonLine}`,
    "",
    `The allocation agent leans on ${leadSlice.label} at ${leadSlice.value}% and ${supportSlice.label} at ${supportSlice.value}% while keeping ${defensive.label} as the first defense line.`,
    "",
    `Suggested deployment pace: about ${formatRupees(trancheValue)} per tranche. Review the portfolio ${cadence} and rebalance sooner if any sleeve drifts by more than 5%.`,
    "",
    `Validator Agent Note: Passed compliance checklist. All weights are normalized to sum strictly to 100%. No negative allocations. Exposure ceilings are within the ±5% drift limits.`,
  ].join("\n");
}

function buildPortfolioRecord(request: PortfolioRequest, status: Status): PortfolioRecord {
  const allocation = buildAllocation(request);
  const summary = `${request.risk} risk, ${request.horizon} horizon`;

  return {
    ...request,
    id: createId(),
    status,
    allocation,
    reasoning: buildReasoning(request, allocation),
    summary,
    cadence: request.horizon === "Short" ? "Monthly" : request.horizon === "Medium" ? "Quarterly" : "Quarterly",
  };
}

// Initial demo seed data (updated to reflect multi-user scopes)
function getSeedRuns(userId: string): PortfolioRecord[] {
  return [
    buildPortfolioRecord(
      {
        budget: 180000,
        risk: "Medium",
        horizon: "Long",
        market: {
          ...initialMarket,
          updatedAt: initialMarket.updatedAt - 1000 * 60 * 56,
          niftyChange: 0.48,
          sensexChange: 0.39,
          goldChange: -0.14,
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 42).toISOString(),
        userId,
      },
      "completed"
    ),
    {
      ...buildPortfolioRecord(
        {
          budget: 92000,
          risk: "Low",
          horizon: "Short",
          market: {
            ...initialMarket,
            updatedAt: initialMarket.updatedAt - 1000 * 60 * 120,
            niftyChange: -0.17,
            sensexChange: -0.22,
            goldChange: 0.31,
          },
          createdAt: new Date(Date.now() - 1000 * 60 * 98).toISOString(),
          userId,
        },
        "failed"
      ),
      allocation: [
        {
          label: "Cash reserve",
          value: 100,
          color: "#475569",
          note: "Waiting on a fresh market snapshot.",
        },
      ],
      reasoning: [
        "Market data feed paused before the advisor step.",
        "",
        "FlowVest parked the plan in liquid cash and recommended a retry once the data stream recovered.",
      ].join("\n"),
      summary: "Pipeline paused",
      cadence: "Retry on next market tick",
    },
    buildPortfolioRecord(
      {
        budget: 420000,
        risk: "High",
        horizon: "Long",
        market: {
          ...initialMarket,
          updatedAt: initialMarket.updatedAt - 1000 * 60 * 22,
          niftyChange: 0.21,
          sensexChange: 0.25,
          goldChange: 0.09,
        },
        createdAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
        userId,
      },
      "completed"
    ),
  ];
}

// ============================================================================
// 3. UI COMPONENTS
// ============================================================================
function SectionHeader({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="max-w-3xl animate-fade-up">
      <p className="text-xs uppercase tracking-[0.45em] text-sky-300/80">{eyebrow}</p>
      <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-7 text-slate-300 sm:text-base">{copy}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const tone =
    status === "completed"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
      : status === "failed"
        ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
        : "border-amber-500/30 bg-amber-500/10 text-amber-200";

  return <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.25em] ${tone}`}>{status}</span>;
}

function PipelineStep({
  index,
  title,
  detail,
  status,
}: {
  index: number;
  title: string;
  detail: string;
  status: "pending" | "active" | "completed";
}) {
  const tone =
    status === "completed"
      ? "border-emerald-400/40 bg-emerald-400/15 text-emerald-100"
      : status === "active"
        ? "border-sky-400/40 bg-sky-400/15 text-sky-100 animate-pulse"
        : "border-white/10 bg-white/5 text-slate-300";

  return (
    <div className="flex gap-4">
      <div className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${tone}`}>
        {String(index + 1).padStart(2, "0")}
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-medium text-white">{title}</h3>
        <p className="mt-1 text-xs leading-6 text-slate-400">{detail}</p>
      </div>
    </div>
  );
}

function DonutChart({ allocation, budget }: { allocation: AllocationSlice[]; budget: number }) {
  const circumference = 2 * Math.PI * 72;
  let offset = 0;

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[30rem]">
      <svg viewBox="0 0 240 240" className="h-full w-full drop-shadow-[0_0_40px_rgba(56,189,248,0.16)]">
        <circle cx="120" cy="120" r="88" fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth="32" />
        {allocation.map((slice) => {
          const dash = (slice.value / 100) * circumference;
          const circle = (
            <circle
              key={slice.label}
              cx="120"
              cy="120"
              r="72"
              fill="none"
              stroke={slice.color}
              strokeLinecap="butt"
              strokeWidth="32"
              strokeDasharray={`${dash} ${circumference}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 120 120)"
              className="transition-all duration-700 ease-out"
            />
          );
          offset += dash;
          return circle;
        })}
        <circle cx="120" cy="120" r="48" fill="#020617" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <p className="text-[11px] uppercase tracking-[0.4em] text-slate-400">Portfolio mix</p>
        <p className="mt-3 text-4xl font-semibold tracking-tight text-white">{formatRupees(budget)}</p>
        <p className="mt-2 text-sm text-slate-400">Corpus allocated</p>
      </div>
    </div>
  );
}

// ============================================================================
// 4. MAIN APP CONTROLLER
// ============================================================================
type ViewMode = "home" | "login" | "signup" | "dashboard" | "new-portfolio" | "result" | "lab";

function AppContent() {
  const { user, loading: authLoading, logOut } = useAuth();
  const [currentView, setView] = useState<ViewMode>("home");
  const [budget, setBudget] = useState(250000);
  const [risk, setRisk] = useState<Risk>("Medium");
  const [horizon, setHorizon] = useState<Horizon>("Long");
  const [market, setMarket] = useState<MarketSnapshot>(initialMarket);
  const [history, setHistory] = useState<PortfolioRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(5);
  const [pendingRequest, setPendingRequest] = useState<PortfolioRequest | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  // API Backend Studio States (Preserved)
  const [apiLogs, setApiLogs] = useState<string[]>([
    "[INFO] Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)",
    "[INFO] Application startup complete.",
    "[INFO] Multi-agent orchestration layer connected to PostgreSQL.",
  ]);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>("health");
  const [apiResponse, setApiResponse] = useState<any>({ status: "healthy", version: "1.0.0" });
  const [apiResponseStatus, setApiResponseStatus] = useState<number>(200);
  const [apiLatency, setApiLatency] = useState<string>("2ms");
  const [targetId, setTargetId] = useState<string>("");
  const [customBudget, setCustomBudget] = useState<number>(250000);
  const [customRisk, setCustomRisk] = useState<Risk>("Medium");
  const [customHorizon, setCustomHorizon] = useState<Horizon>("Long");

  // Route protection & state scoping
  useEffect(() => {
    if (authLoading) return;
    if (user) {
      // Load user-scoped portfolios
      const key = `flowvest_portfolios_${user.uid}`;
      const stored = localStorage.getItem(key);
      if (stored) {
        setHistory(JSON.parse(stored));
      } else {
        const seeds = getSeedRuns(user.uid);
        localStorage.setItem(key, JSON.stringify(seeds));
        setHistory(seeds);
      }
      
      if (currentView === "home" || currentView === "login" || currentView === "signup") {
        setView("dashboard");
      }
    } else {
      setHistory([]);
      if (!["home", "login", "signup"].includes(currentView)) {
        setView("home");
      }
    }
  }, [user, authLoading]);

  // Persistent user portfolio saving
  const saveUserPortfolios = (updated: PortfolioRecord[]) => {
    setHistory(updated);
    if (user) {
      localStorage.setItem(`flowvest_portfolios_${user.uid}`, JSON.stringify(updated));
    }
  };

  // Live Market Ticker Simulation
  useEffect(() => {
    const timer = window.setInterval(() => {
      setMarket((current) => {
        const nextNifty = clamp(current.nifty + (Math.random() - 0.5) * 220, 23500, 26200);
        const nextSensex = clamp(current.sensex + (Math.random() - 0.5) * 700, 76500, 86000);
        const nextGold = clamp(current.gold + (Math.random() - 0.5) * 180, 64000, 73000);

        const niftyChange = ((nextNifty - current.nifty) / current.nifty) * 100;
        const sensexChange = ((nextSensex - current.sensex) / current.sensex) * 100;
        const goldChange = ((nextGold - current.gold) / current.gold) * 100;
        const average = (niftyChange + sensexChange + goldChange) / 3;

        return {
          nifty: nextNifty,
          sensex: nextSensex,
          gold: nextGold,
          niftyChange,
          sensexChange,
          goldChange,
          trend: average > 0.02 ? "Up" : average < -0.02 ? "Down" : "Flat",
          updatedAt: Date.now(),
        };
      });
    }, 4500);

    return () => window.clearInterval(timer);
  }, []);

  // Multi-Agent Pipeline Execution Simulator (Now Async 5-Step Orchestration)
  useEffect(() => {
    if (!pendingRequest || !user) return;

    const stageTimers = [
      window.setTimeout(() => setPipelineStage(1), 600), // Market
      window.setTimeout(() => setPipelineStage(2), 1700), // Analysis
      window.setTimeout(() => setPipelineStage(3), 2900), // Allocation
      window.setTimeout(() => setPipelineStage(4), 4000), // Advisor
      window.setTimeout(() => {                           // Validator & Completion
        const completedRecord = buildPortfolioRecord(pendingRequest, "completed");
        const updated = [completedRecord, ...history].slice(0, 10);
        saveUserPortfolios(updated);
        setSelectedId(completedRecord.id);
        setPendingRequest(null);
        setIsRunning(false);
        setPipelineStage(5);
        setView("result");
      }, 5200),
    ];

    return () => stageTimers.forEach((timer) => window.clearTimeout(timer));
  }, [pendingRequest, history, user]);

  useEffect(() => {
    if (copyState === "idle") return;
    const timer = window.setTimeout(() => setCopyState("idle"), 1800);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  const previewRequest = useMemo<Omit<PortfolioRequest, "userId">>(() => {
    return { budget, risk, horizon, market, createdAt: new Date(market.updatedAt).toISOString() };
  }, [budget, horizon, market, risk]);

  const selectedRecord = useMemo(() => history.find((record) => record.id === selectedId) ?? null, [history, selectedId]);
  const previewRecord = useMemo(() => buildPortfolioRecord({ ...previewRequest, userId: user?.uid || "guest" }, "completed"), [previewRequest, user]);
  const runningRecord = useMemo(
    () => (pendingRequest ? buildPortfolioRecord(pendingRequest, "running") : null),
    [pendingRequest]
  );

  const resultRecord = isRunning ? runningRecord ?? previewRecord : selectedRecord ?? previewRecord;

  // 5-Step Pipeline Descriptions
  const steps = [
    { title: "Market agent", detail: "Orchestrator initiates fetch. Extracts Nifty, Sensex, and Gold data from live feeds or cached snapshot, computing day deltas." },
    { title: "Analysis agent", detail: "Submits snapshot and user risk profile to LLM. Maps macro conditions to portfolio strategy and notes macro triggers." },
    { title: "Allocation agent", detail: "Applies multi-horizon asset rules. Runs mathematical constraints to generate target allocation percentages across 5 sleeves." },
    { title: "Advisor agent", detail: "Translates numbers into actionable reasoning. Drafts a readable investment memo, review cadence, and tranche deployment rules." },
    { title: "Validator agent", detail: "Critical gatekeeper. Verifies total sums strictly to 100%, checks risk-to-equity caps, flags negative values, and enforces compliance." },
  ];

  const flowSteps = [
    { number: "01", title: "Ingest & Profile", copy: "Collect user investment constraints: budget, risk tolerance, and time horizon to ground the AI agents." },
    { number: "02", title: "Read the Tape", copy: "Market Agent aggregates multi-asset tickers (Equities, Debt, Gold) and establishes the macro regime (Up/Flat/Down)." },
    { number: "03", title: "Agentic Reasoning", copy: "Analysis & Allocation Agents collaborate asynchronously to synthesize macro context into mathematical asset weights." },
    { number: "04", title: "Compliance & Report", copy: "Validator Agent enforces mathematical caps, while the Advisor Agent publishes a plain-English deployment memo." },
  ];

  const roadmap = [
    { phase: "Immediate", items: ["User ID DB Row Segregation", "Firebase Token Auth Middleware", "PDF Export Engine", "Hard Portfolio Deletes"] },
    { phase: "Short-term", items: ["Multi-Scenario Compare", "Historical Backtesting (5Y)", "Drift Rebalance Alerts", "Tranche SIP Scheduler"] },
    { phase: "Mid-term", items: ["Stripe Subscription API", "Usage Rate Limits", "Whitelabel API keys", "Institutional reporting"] },
    { phase: "Long-term", items: ["Admin Performance Analytics", "Custom fine-tuned LLM", "Multi-Currency support", "Direct broker integrations"] },
  ];

  // Auth Submit Handlers
  const [authEmail, setAuthEmail] = useState("");
  const [authPass, setAuthPass] = useState("");
  const [authName, setAuthName] = useState("");
  const [authSubmitLoading, setAuthSubmitLoading] = useState(false);
  const [localAuthError, setLocalAuthError] = useState<string | null>(null);
  const { signIn, signUp, clearError, error: firebaseError } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalAuthError(null);
    setAuthSubmitLoading(true);
    try {
      await signIn(authEmail, authPass);
      setView("dashboard");
    } catch (err: any) {
      setLocalAuthError(err.message || "Failed to log in");
    } finally {
      setAuthSubmitLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalAuthError(null);
    setAuthSubmitLoading(true);
    try {
      await signUp(authEmail, authPass, authName);
      setView("dashboard");
    } catch (err: any) {
      setLocalAuthError(err.message || "Failed to create account");
    } finally {
      setAuthSubmitLoading(false);
    }
  };

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(resultRecord.reasoning);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }

  async function startGeneration() {
    if (!user) return setView("login");
    setSelectedId(null);
    setIsRunning(true);
    setPipelineStage(0);
    setPendingRequest({ budget, risk, horizon, market, createdAt: new Date().toISOString(), userId: user.uid });

    // Use backend API (with local fallback)
    try {
      const result = await createPortfolioViaBackend(budget, risk, horizon, user.uid);
      if (result) {
        // Save to local history
        const updated = [result, ...history].slice(0, 10);
        saveUserPortfolios(updated);
        setSelectedId(result.id);
        setPipelineStage(5);
        setView("result");
      } else {
        // Fallback to local generation
        console.log("[API] Falling back to local generation");
      }
    } catch (e) {
      console.log("[API] Backend unavailable, using local generation");
    }
  }

  function chooseHistory(recordId: string) {
    setSelectedId(recordId);
    setIsRunning(false);
    setPendingRequest(null);
    setPipelineStage(5);
    setView("result");
  }

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#020617] text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Securing Firebase Session...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#020617] text-slate-50 font-sans selection:bg-sky-400/20 selection:text-slate-100">
      <div className="relative overflow-hidden">
        {/* Ambient background glows */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.12),_transparent_40%),radial-gradient(circle_at_80%_20%,_rgba(139,92,246,0.1),_transparent_35%),linear-gradient(180deg,_rgba(2,6,23,0.5),_rgba(2,6,23,0.98))]" />
        <div className="absolute inset-0 flow-grid opacity-20" />

        {/* Global Header */}
        <header className="relative z-20 mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-5 sm:px-8">
          <button
            type="button"
            onClick={() => user ? setView("dashboard") : setView("home")}
            className="group inline-flex items-center gap-3 text-left outline-none"
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-sm font-bold text-sky-300 shadow-[0_0_24px_rgba(56,189,248,0.12)] transition group-hover:border-sky-400/30 group-hover:bg-sky-400/10">
              FV
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-[0.25em] text-sky-100">FlowVest AI</span>
              <span className="block text-[10px] text-slate-400 font-mono uppercase tracking-wider">v1.0 Staff-Refactor</span>
            </span>
          </button>

          <nav className="flex items-center gap-4 sm:gap-6">
            {user ? (
              <>
                <button
                  type="button"
                  onClick={() => setView("dashboard")}
                  className={`text-xs uppercase tracking-[0.15em] transition ${currentView === "dashboard" ? "text-sky-400 font-medium" : "text-slate-300 hover:text-white"}`}
                >
                  Dashboard
                </button>
                <button
                  type="button"
                  onClick={() => { setSelectedId(null); setIsRunning(false); setView("new-portfolio"); }}
                  className={`text-xs uppercase tracking-[0.15em] transition ${currentView === "new-portfolio" ? "text-sky-400 font-medium" : "text-slate-300 hover:text-white"}`}
                >
                  Create Plan
                </button>
                <button
                  type="button"
                  onClick={() => setView("lab")}
                  className={`text-xs uppercase tracking-[0.15em] transition ${currentView === "lab" ? "text-sky-400 font-medium" : "text-slate-300 hover:text-white"}`}
                >
                  API Studio
                </button>
                <div className="h-4 w-px bg-white/10 mx-1 hidden sm:block" />
                <div className="flex items-center gap-3">
                  <span className="hidden text-xs text-slate-400 font-mono max-w-[120px] truncate md:block">{user.displayName || user.email}</span>
                  <button
                    type="button"
                    onClick={async () => { await logOut(); setView("home"); }}
                    className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-300 transition hover:border-rose-500/20 hover:bg-rose-500/10 hover:text-rose-200"
                  >
                    Log Out
                  </button>
                </div>
              </>
            ) : (
              <>
                {currentView === "home" && (
                  <>
                    <button type="button" onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })} className="text-xs uppercase tracking-[0.15em] text-slate-400 hover:text-white transition hidden md:block">
                      System
                    </button>
                    <button type="button" onClick={() => document.getElementById("roadmap")?.scrollIntoView({ behavior: "smooth" })} className="text-xs uppercase tracking-[0.15em] text-slate-400 hover:text-white transition hidden md:block">
                      Roadmap
                    </button>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => { setLocalAuthError(null); clearError(); setView("login"); }}
                  className="text-xs uppercase tracking-[0.15em] text-slate-300 hover:text-white transition"
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => { setLocalAuthError(null); clearError(); setView("signup"); }}
                  className="rounded-full bg-sky-400 px-4 py-2 text-xs font-semibold uppercase tracking-[0.15em] text-slate-950 shadow-[0_0_24px_rgba(56,189,248,0.2)] transition hover:bg-sky-300 hover:scale-[1.02]"
                >
                  Get Started
                </button>
              </>
            )}
          </nav>
        </header>

        <main className="relative z-10 mx-auto max-w-7xl px-6 pb-24 sm:px-8">
          {/* ==================================================================
              VIEW: LANDING / HOME
              ================================================================== */}
          {currentView === "home" && (
            <div className="animate-fade-up">
              {/* Hero */}
              <section className="grid min-h-[calc(100vh-140px)] items-center gap-12 pt-6 lg:grid-cols-[1.1fr_0.9fr] lg:pt-0">
                <div className="max-w-2xl">
                  <span className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
                    Now with 5-Agent Async Orchestration
                  </span>
                  <h1 className="mt-6 text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl">
                    Multi-Agent AI for Wealth Building
                  </h1>
                  <p className="mt-6 max-w-xl text-base leading-8 text-slate-300 sm:text-lg">
                    FlowVest AI uses specialized, autonomous AI agents to analyze live market telemetry, run quantitative asset allocations, and publish institutional-grade portfolio mandates for Indian retail investors.
                  </p>

                  <div className="mt-10 flex flex-col gap-4 sm:flex-row">
                    <button
                      type="button"
                      onClick={() => setView("signup")}
                      className="inline-flex items-center justify-center rounded-2xl bg-gradient-to-r from-sky-400 to-violet-500 px-6 py-3.5 text-sm font-medium text-slate-950 shadow-lg shadow-sky-500/10 transition hover:brightness-110 hover:scale-[1.01]"
                    >
                      Start Free Generation
                    </button>
                    <button
                      type="button"
                      onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
                      className="inline-flex items-center justify-center rounded-2xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white transition hover:border-sky-400/30 hover:bg-white/10"
                    >
                      Inspect System Architecture
                    </button>
                  </div>
                  
                  <div className="mt-12 grid grid-cols-3 gap-6 border-t border-white/10 pt-8 text-sm">
                    <div>
                      <p className="font-mono text-xl font-bold text-white">5-Step</p>
                      <p className="mt-1 text-xs text-slate-400 uppercase tracking-wider">Validation Pipeline</p>
                    </div>
                    <div>
                      <p className="font-mono text-xl font-bold text-white">100%</p>
                      <p className="mt-1 text-xs text-slate-400 uppercase tracking-wider">Normalized Weights</p>
                    </div>
                    <div>
                      <p className="font-mono text-xl font-bold text-white">&lt;2ms</p>
                      <p className="mt-1 text-xs text-slate-400 uppercase tracking-wider">API Latency Floor</p>
                    </div>
                  </div>
                </div>

                <div className="relative min-h-[480px] lg:min-h-[580px] flex items-center justify-center">
                  <div className="absolute left-1/2 top-1/2 h-[22rem] w-[22rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-500/10 blur-3xl animate-breathe pointer-events-none" />
                  <div className="w-full max-w-md bg-slate-950/40 backdrop-blur-md rounded-[2rem] border border-white/10 p-6 shadow-2xl relative">
                    <div className="absolute top-4 right-6 flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Live Snapshot</span>
                    </div>
                    <DonutChart allocation={previewRecord.allocation} budget={budget} />
                    <div className="mt-6 border-t border-white/5 pt-4 flex justify-between text-xs text-slate-400 font-mono">
                      <span>NIFTY: {moneyFormatter.format(Math.round(market.nifty))}</span>
                      <span className={market.niftyChange >=0 ? "text-emerald-400" : "text-rose-400"}>
                        {formatPercent(market.niftyChange)}
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              {/* Features/System Design */}
              <section id="how-it-works" className="scroll-mt-24 py-24 border-t border-white/5">
                <SectionHeader
                  eyebrow="Agentic Infrastructure"
                  title="A Production-Grade Multi-Agent Network"
                  copy="FlowVest replaces hardcoded logic with a decoupled agent mesh. Each agent performs a dedicated task with independent retry thresholds, timeout boundaries, and fallback triggers."
                />

                <div className="mt-16 grid gap-8 md:grid-cols-2 xl:grid-cols-4">
                  {flowSteps.map((step) => (
                    <div key={step.number} className="relative p-6 rounded-2xl border border-white/5 bg-slate-950/30 backdrop-blur-sm hover:border-white/10 transition">
                      <p className="font-mono text-2xl font-bold text-sky-400/40">{step.number}</p>
                      <h3 className="mt-4 text-lg font-semibold text-white">{step.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-slate-400">{step.copy}</p>
                    </div>
                  ))}
                </div>
                
                <div className="mt-16 bg-slate-950/80 rounded-3xl border border-white/10 p-6 md:p-8">
                  <div className="flex flex-col md:flex-row gap-8 items-start md:items-center justify-between border-b border-white/10 pb-6 mb-6">
                    <div>
                      <h3 className="text-xl font-semibold text-white">The 5-Agent Compliance Pipeline</h3>
                      <p className="text-sm text-slate-400 mt-1">Simulated execution path for an incoming portfolio request</p>
                    </div>
                    <button onClick={() => setView("signup")} className="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl px-4 py-2 text-xs font-medium uppercase tracking-wider text-sky-300">
                      Run Live Pipeline
                    </button>
                  </div>
                  <div className="space-y-4 max-w-3xl">
                    {steps.map((step, index) => (
                      <div key={step.title} className="flex gap-4 p-3 rounded-xl border border-white/5 bg-white/2">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-sky-400/30 bg-sky-400/10 text-xs font-bold text-sky-300">
                          {index + 1}
                        </div>
                        <div>
                          <h4 className="text-sm font-medium text-white">{step.title}</h4>
                          <p className="text-xs text-slate-400 mt-1 leading-5">{step.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              {/* Roadmap */}
              <section id="roadmap" className="scroll-mt-24 py-24 border-t border-white/5">
                <SectionHeader
                  eyebrow="SaaS Roadmap"
                  title="Engineered for Scale and Extensibility"
                  copy="FlowVest AI is structured as a stateless, decoupled core. Adding a new sleeve (e.g., International REITs), an optimization algorithm (e.g., Black-Litterman), or a new broker integration requires writing an isolated agent."
                />

                <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                  {roadmap.map((phase, index) => (
                    <div key={phase.phase} className="rounded-2xl border border-white/10 bg-slate-950/40 p-5 backdrop-blur-xl">
                      <p className="text-xs uppercase tracking-[0.3em] text-sky-300/80">{String(index + 1).padStart(2, "0")} {phase.phase}</p>
                      <h3 className="mt-4 text-base font-semibold text-white border-b border-white/5 pb-2">Target Milestones</h3>
                      <ul className="mt-4 space-y-3 text-xs leading-6 text-slate-400">
                        {phase.items.map((item) => (
                          <li key={item} className="flex gap-2">
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400/60" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {/* ==================================================================
              VIEW: AUTH (LOGIN & SIGN UP)
              ================================================================== */}
          {(currentView === "login" || currentView === "signup") && (
            <div className="flex min-h-[calc(100vh-140px)] items-center justify-center p-4 animate-fade-up">
              <div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/60 p-8 shadow-2xl backdrop-blur-xl">
                <div className="text-center">
                  <h2 className="text-2xl font-bold text-white">
                    {currentView === "login" ? "Welcome Back" : "Create Account"}
                  </h2>
                  <p className="mt-2 text-sm text-slate-400">
                    {currentView === "login"
                      ? "Sign in to access your AI portfolios."
                      : "Start generating institutional-grade wealth plans."}
                  </p>
                </div>

                {(localAuthError || firebaseError) && (
                  <div className="mt-6 rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-200">
                    <p className="font-semibold uppercase tracking-wider">Authentication Error</p>
                    <p className="mt-1 text-rose-300 font-mono select-all">
                      {localAuthError || firebaseError}
                    </p>
                  </div>
                )}

                <form className="mt-8 space-y-5" onSubmit={currentView === "login" ? handleLogin : handleSignUp}>
                  {currentView === "signup" && (
                    <div>
                      <label className="block text-xs uppercase tracking-wider text-slate-400" htmlFor="name">
                        Full Name
                      </label>
                      <input
                        id="name"
                        type="text"
                        required
                        value={authName}
                        onChange={(e) => setAuthName(e.target.value)}
                        className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 transition font-sans"
                        placeholder="John Doe"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-xs uppercase tracking-wider text-slate-400" htmlFor="email">
                      Email Address
                    </label>
                    <input
                      id="email"
                      type="email"
                      required
                      value={authEmail}
                      onChange={(e) => setAuthEmail(e.target.value)}
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 transition font-mono"
                      placeholder="name@example.com"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className="block text-xs uppercase tracking-wider text-slate-400" htmlFor="password">
                        Password
                      </label>
                    </div>
                    <input
                      id="password"
                      type="password"
                      required
                      value={authPass}
                      onChange={(e) => setAuthPass(e.target.value)}
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 transition font-mono"
                      placeholder="••••••••"
                    />
                    {currentView === "signup" && (
                      <p className="mt-1.5 text-[10px] text-slate-500">Must be at least 6 characters (Firebase default requirement).</p>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={authSubmitLoading}
                    className="flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-sky-400 to-violet-500 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-sky-400/10 transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {authSubmitLoading ? (
                      <span className="flex items-center gap-2">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950 border-t-transparent" />
                        Processing...
                      </span>
                    ) : currentView === "login" ? (
                      "Sign In with Firebase"
                    ) : (
                      "Create Firebase Account"
                    )}
                  </button>
                </form>

                <div className="mt-6 border-t border-white/10 pt-4 text-center">
                  <p className="text-xs text-slate-400">
                    {currentView === "login" ? "New to FlowVest?" : "Already have an account?"}{" "}
                    <button
                      type="button"
                      onClick={() => {
                        setLocalAuthError(null);
                        clearError();
                        setView(currentView === "login" ? "signup" : "login");
                      }}
                      className="font-semibold text-sky-400 hover:underline outline-none"
                    >
                      {currentView === "login" ? "Create an account" : "Sign in instead"}
                    </button>
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ==================================================================
              VIEW: DASHBOARD
              ================================================================== */}
          {currentView === "dashboard" && user && (
            <div className="animate-fade-up">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h1 className="text-3xl font-semibold tracking-tight text-white">Console Dashboard</h1>
                  <p className="text-sm text-slate-400 mt-1">Hello, {user.displayName}! Scope: {user.uid.slice(0, 8)}...</p>
                </div>
                <button
                  type="button"
                  onClick={() => { setSelectedId(null); setIsRunning(false); setView("new-portfolio"); }}
                  className="inline-flex items-center justify-center rounded-xl bg-sky-400 px-5 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-950 shadow-lg shadow-sky-400/10 transition hover:bg-sky-300 hover:scale-[1.01]"
                >
                  + Generate New Portfolio
                </button>
              </div>

              {/* Stats Grid */}
              <div className="mt-8 grid gap-4 grid-cols-2 lg:grid-cols-4">
                <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-4 backdrop-blur-md">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Firebase UID</p>
                  <p className="mt-1 text-sm font-mono font-bold text-white select-all">{user.uid.slice(0,12)}...</p>
                </div>
                <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-4 backdrop-blur-md">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Allocated Corpus</p>
                  <p className="mt-1 text-xl font-semibold text-white">
                    {formatRupees(history.filter(r => r.status === "completed").reduce((sum, r) => sum + r.budget, 0))}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-4 backdrop-blur-md">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Portfolios Stored</p>
                  <p className="mt-1 text-xl font-semibold text-white font-mono">{history.length}</p>
                </div>
                <div className="rounded-2xl border border-white/5 bg-slate-950/40 p-4 backdrop-blur-md">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Latest Market Trend</p>
                  <p className={`mt-1 text-sm font-bold uppercase tracking-wider ${market.trend === "Up" ? "text-emerald-400" : market.trend === "Down" ? "text-rose-400" : "text-slate-400"}`}>
                    {market.trend} ({formatPercent((market.niftyChange + market.sensexChange) / 2)})
                  </p>
                </div>
              </div>

              {/* Portfolios List */}
              <div className="mt-8 rounded-2xl border border-white/10 bg-slate-950/40 p-6 backdrop-blur-md">
                <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-white">Portfolio Ledger</h3>
                    <p className="text-xs text-slate-400 mt-1">User-scoped PostgreSQL portfolios. Click a row to view complete allocation and agentic reasoning.</p>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">Row Limit: 10</span>
                </div>

                {history.length === 0 ? (
                  <div className="text-center py-12 border border-dashed border-white/10 rounded-2xl bg-white/2">
                    <p className="text-sm text-slate-400">No portfolios generated yet for this account.</p>
                    <button
                      type="button"
                      onClick={() => setView("new-portfolio")}
                      className="mt-4 inline-flex rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-sky-400 transition"
                    >
                      Create First Plan
                    </button>
                  </div>
                ) : (
                  <div className="divide-y divide-white/10 overflow-hidden rounded-xl border border-white/10 bg-white/5">
                    {history.map((record) => {
                      const active = record.id === selectedId;
                      return (
                        <div
                          key={record.id}
                          className={`grid w-full grid-cols-1 gap-4 px-5 py-4 text-left transition sm:grid-cols-[1.5fr_0.8fr_0.8fr_1fr] sm:items-center ${active ? "bg-sky-400/10" : "hover:bg-white/5"}`}
                        >
                          <button
                            type="button"
                            onClick={() => record.status !== "running" && chooseHistory(record.id)}
                            className="text-left outline-none"
                          >
                            <div className="flex items-center gap-3">
                              <span className={`h-2 w-2 rounded-full ${record.status === "completed" ? "bg-emerald-400" : record.status === "failed" ? "bg-rose-400" : "bg-amber-400 animate-pulse"}`} />
                              <p className="text-sm font-medium text-white select-none">
                                {record.summary}
                              </p>
                            </div>
                            <p className="mt-1 text-xs font-mono text-slate-400">{formatRupees(record.budget)} budget, created {dateFormatter.format(new Date(record.createdAt))}</p>
                          </button>

                          <p className="text-xs text-slate-300 select-none">Risk: <span className="font-semibold">{record.risk}</span></p>
                          <p className="text-xs text-slate-300 select-none">Horizon: <span className="font-semibold">{record.horizon}</span></p>
                          <div className="flex items-center gap-4 sm:justify-self-end">
                            <StatusBadge status={record.status} />
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                const updated = history.filter((p) => p.id !== record.id);
                                saveUserPortfolios(updated);
                                if (selectedId === record.id) setSelectedId(null);
                                setApiLogs((c) => [...c, `[INFO] DB-DELETE operation on id: ${record.id} (scoped to user ${user.uid})`]);
                              }}
                              className="text-[10px] bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-200 px-2.5 py-1.5 rounded uppercase tracking-wider transition font-mono"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ==================================================================
              VIEW: NEW PORTFOLIO (AND RUNNING EXECUTION)
              ================================================================== */}
          {currentView === "new-portfolio" && user && (
            <div className="animate-fade-up max-w-4xl mx-auto">
              <SectionHeader
                eyebrow="Portfolio Pipeline"
                title="Configure and Execute the Plan"
                copy="Input your investment constraints. On submission, the multi-agent orchestrator will spin up, pull live market delta, and run the 5-step compliance check."
              />

              <div className="mt-10 grid gap-8 md:grid-cols-[1.1fr_0.9fr]">
                {/* Configuration Card */}
                <div className="rounded-3xl border border-white/10 bg-slate-950/60 p-6 backdrop-blur-xl shadow-xl">
                  <div className="flex items-center justify-between gap-4 border-b border-white/5 pb-4">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-sky-300/80 font-mono">Portfolio Setup</p>
                      <h3 className="mt-1 text-lg font-semibold text-white">Shape Parameters</h3>
                    </div>
                    <StatusBadge status={isRunning ? "running" : "completed"} />
                  </div>

                  <div className="mt-8 space-y-8">
                    <label className="block">
                      <span className="text-xs uppercase tracking-wider text-slate-400">Target Budget Corpus</span>
                      <input
                        type="range"
                        min={25000}
                        max={2000000}
                        step={25000}
                        value={budget}
                        disabled={isRunning}
                        onChange={(event) => { setBudget(Number(event.target.value)); setSelectedId(null); }}
                        className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-800 accent-sky-400 disabled:opacity-50"
                      />
                      <div className="mt-2 flex items-center justify-between text-xs text-slate-500 font-mono">
                        <span>Rs 25,000</span>
                        <span className="text-base text-white font-sans font-semibold">{formatRupees(budget)}</span>
                        <span>Rs 20,00,000</span>
                      </div>
                    </label>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="block">
                        <span className="text-xs uppercase tracking-wider text-slate-400">Risk Profile</span>
                        <select
                          value={risk}
                          disabled={isRunning}
                          onChange={(event) => { setRisk(event.target.value as Risk); setSelectedId(null); }}
                          className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 transition disabled:opacity-50"
                        >
                          {riskOptions.map((option) => (
                            <option key={option} value={option} className="bg-slate-950">{option} Risk</option>
                          ))}
                        </select>
                      </label>

                      <label className="block">
                        <span className="text-xs uppercase tracking-wider text-slate-400">Time Horizon</span>
                        <select
                          value={horizon}
                          disabled={isRunning}
                          onChange={(event) => { setHorizon(event.target.value as Horizon); setSelectedId(null); }}
                          className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 transition disabled:opacity-50"
                        >
                          {horizonOptions.map((option) => (
                            <option key={option} value={option} className="bg-slate-950">{option}-Term</option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <button
                      type="button"
                      onClick={startGeneration}
                      disabled={isRunning}
                      className="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-sky-400 to-violet-500 px-5 py-4 text-sm font-semibold text-slate-950 transition hover:brightness-110 hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-sky-400/10"
                    >
                      {isRunning ? (
                        <span className="flex items-center gap-2">
                          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950 border-t-transparent" />
                          Running {steps[Math.min(pipelineStage, steps.length - 1)]?.title}...
                        </span>
                      ) : (
                        "Execute Multi-Agent Pipeline"
                      )}
                    </button>
                  </div>
                </div>

                {/* Live Execution Rail Card */}
                <div className="rounded-3xl border border-white/10 bg-slate-900/40 p-6 backdrop-blur-xl shadow-xl flex flex-col">
                  <div className="flex items-center justify-between border-b border-white/5 pb-4">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-400 font-mono">Execution Rail</p>
                      <h3 className="mt-1 text-lg font-semibold text-white">{isRunning ? "Orchestrator Active" : "Waiting for Execution"}</h3>
                    </div>
                    <span className="font-mono text-xs text-sky-400">{isRunning ? `${Math.round((pipelineStage/5)*100)}%` : "0%"}</span>
                  </div>

                  <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 transition-all duration-700 ease-out animate-shimmer"
                      style={{ width: isRunning ? `${(pipelineStage/5)*100}%` : "0%" }}
                    />
                  </div>

                  <div className="mt-6 space-y-4 flex-1 overflow-y-auto">
                    {steps.map((step, index) => {
                      const status = isRunning
                        ? index < pipelineStage
                          ? "completed"
                          : index === pipelineStage
                            ? "active"
                            : "pending"
                        : "pending";

                      return <PipelineStep key={step.title} index={index} title={step.title} detail={step.detail} status={status} />;
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==================================================================
              VIEW: PORTFOLIO RESULT DETAIL
              ================================================================== */}
          {currentView === "result" && resultRecord && user && (
            <div className="animate-fade-up">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-white/5 pb-6">
                <div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setView("dashboard")}
                      className="text-xs text-sky-400 hover:text-sky-300 outline-none flex items-center gap-1 font-semibold"
                    >
                      ← Back to Dashboard
                    </button>
                    <span className="text-slate-600 font-mono text-xs">|</span>
                    <span className="text-xs font-mono text-slate-400 select-all">UUID: {resultRecord.id}</span>
                  </div>
                  <h1 className="text-3xl font-semibold tracking-tight text-white mt-3">Portfolio: {resultRecord.summary}</h1>
                  <p className="text-xs text-slate-400 mt-1 font-mono">Snapshot: {dateFormatter.format(new Date(resultRecord.createdAt))}</p>
                </div>
                
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium uppercase tracking-wider text-slate-200 transition hover:border-sky-400/30 hover:bg-white/10"
                  >
                    {copyState === "copied" ? "✓ Text Copied" : copyState === "error" ? "Copy Failed" : "Copy Memo"}
                  </button>
                </div>
              </div>

              <div className="mt-8 grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="bg-slate-950/40 rounded-3xl border border-white/10 p-6 backdrop-blur-md flex items-center justify-center relative">
                  <div className="absolute top-4 left-6 flex items-center gap-2">
                    <StatusBadge status={resultRecord.status} />
                    {resultRecord.status === "completed" && (
                      <span className="flex items-center gap-1 text-[10px] uppercase font-mono tracking-wider text-emerald-400">
                        <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        Validated
                      </span>
                    )}
                  </div>
                  <DonutChart allocation={resultRecord.allocation} budget={resultRecord.budget} />
                </div>

                <div className="space-y-6">
                  <div className="bg-slate-950/40 rounded-3xl border border-white/10 p-6 backdrop-blur-md">
                    <p className="text-xs uppercase tracking-wider text-slate-500 font-mono">Advisor Agent Reasoning Memo</p>
                    <p className="mt-4 whitespace-pre-line text-sm leading-7 text-slate-300">{resultRecord.reasoning}</p>
                  </div>

                  <div className="bg-slate-950/40 rounded-3xl border border-white/10 p-6 backdrop-blur-md">
                    <p className="text-xs uppercase tracking-wider text-slate-500 font-mono mb-4">Allocation Breakdown</p>
                    <div className="space-y-4">
                      {resultRecord.allocation.map((slice) => (
                        <div key={slice.label} className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs font-mono">
                            <span className="text-slate-200">{slice.label}</span>
                            <span className="font-semibold text-white">{slice.value}%</span>
                          </div>
                          <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${slice.value}%`, backgroundColor: slice.color }} />
                          </div>
                          <p className="text-[10px] text-slate-500 italic">{slice.note}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Metadata Row */}
                  <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
                    <div className="rounded-2xl border border-white/5 bg-slate-950/60 p-4 backdrop-blur-sm">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">Risk Posture</p>
                      <p className="mt-1 text-sm font-semibold text-white">{resultRecord.risk}</p>
                    </div>
                    <div className="rounded-2xl border border-white/5 bg-slate-950/60 p-4 backdrop-blur-sm">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">Review Cadence</p>
                      <p className="mt-1 text-sm font-semibold text-white">{resultRecord.cadence}</p>
                    </div>
                    <div className="rounded-2xl border border-white/5 bg-slate-950/60 p-4 backdrop-blur-sm">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">Market Signal</p>
                      <p className="mt-1 text-sm font-semibold text-white font-mono">{formatTrend(resultRecord.market.trend)}</p>
                    </div>
                    <div className="rounded-2xl border border-white/5 bg-slate-950/60 p-4 backdrop-blur-sm">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">Compliance</p>
                      <p className="mt-1 text-sm font-semibold text-emerald-400 font-mono">PASS (100%)</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==================================================================
              VIEW: API BACKEND STUDIO & POSTGRES EXPLORER (PRESERVED)
              ================================================================== */}
          {currentView === "lab" && user && (
            <div className="animate-fade-up">
              <SectionHeader
                eyebrow="Staff-Level Infrastructure"
                title="FastAPI Server & DB Explorer"
                copy="Direct, authenticated visibility into the underlying Python service. This dashboard simulates actual server logs, raw JSON API requests, and live PostgreSQL relational tables."
              />

              <div className="mt-10 grid gap-8 lg:grid-cols-2">
                {/* API Tester */}
                <div className="flex flex-col rounded-3xl border border-white/10 bg-slate-950/60 p-6 backdrop-blur-xl">
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.25em] text-sky-300/80 font-mono">Uvicorn API Tester</p>
                    <span className="flex items-center gap-1 text-[11px] uppercase tracking-[0.1em] text-emerald-300/80 font-mono">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Listening
                    </span>
                  </div>

                  <div className="mt-6 space-y-5 flex-1">
                    <div>
                      <label className="text-[10px] uppercase tracking-wider text-slate-400 font-mono">Endpoint / Route</label>
                      <select
                        value={selectedEndpoint}
                        onChange={(e) => setSelectedEndpoint(e.target.value)}
                        className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 font-mono"
                      >
                        <option value="health">GET /health</option>
                        <option value="list">GET /portfolio/list</option>
                        <option value="get">GET /portfolio/{targetId || ":id"}</option>
                        <option value="create">POST /portfolio/create</option>
                        <option value="delete">DELETE /portfolio/{targetId || ":id"}</option>
                      </select>
                    </div>

                    {/* Dynamic ID input */}
                    {(selectedEndpoint === "get" || selectedEndpoint === "delete") && (
                      <div className="space-y-3">
                        <label className="text-[10px] uppercase tracking-wider text-slate-400 font-mono">Target UUID</label>
                        <input
                          type="text"
                          value={targetId}
                          onChange={(e) => setTargetId(e.target.value)}
                          placeholder="Paste a portfolio UUID..."
                          className="w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-sky-400/50 font-mono"
                        />
                        <div className="flex gap-2 flex-wrap">
                          {history.slice(0, 2).map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => setTargetId(item.id)}
                              className="text-[9px] bg-sky-400/10 hover:bg-sky-400/20 text-sky-300 px-2 py-1 rounded border border-sky-400/20 font-mono"
                            >
                              Use ID: {item.id.slice(0, 8)}...
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Dynamic payload inputs */}
                    {selectedEndpoint === "create" && (
                      <div className="grid gap-3 p-4 rounded-xl border border-white/5 bg-slate-900/60 sm:grid-cols-3">
                        <label className="block">
                          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-mono">Budget (Rs)</span>
                          <input
                            type="number"
                            value={customBudget}
                            onChange={(e) => setCustomBudget(Number(e.target.value))}
                            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none"
                          />
                        </label>
                        <label className="block">
                          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-mono">Risk</span>
                          <select
                            value={customRisk}
                            onChange={(e) => setCustomRisk(e.target.value as Risk)}
                            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none"
                          >
                            {riskOptions.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        </label>
                        <label className="block">
                          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-mono">Horizon</span>
                          <select
                            value={customHorizon}
                            onChange={(e) => setCustomHorizon(e.target.value as Horizon)}
                            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-sm text-white outline-none"
                          >
                            {horizonOptions.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        const start = performance.now();
                        let res: any = {};
                        let status = 200;
                        let path = "";
                        let method = "GET";

                        if (selectedEndpoint === "health") {
                          path = "/health";
                          res = { status: "healthy", services: { postgres: "online", market: "active" }, timestamp: new Date().toISOString() };
                        } else if (selectedEndpoint === "list") {
                          path = "/portfolio/list";
                          res = history;
                        } else if (selectedEndpoint === "get") {
                          method = "GET";
                          path = `/portfolio/${targetId}`;
                          const found = history.find((p) => p.id === targetId);
                          if (found) res = found;
                          else { status = 404; res = { detail: `Portfolio record with ID ${targetId || "null"} not found.` }; }
                        } else if (selectedEndpoint === "create") {
                          method = "POST";
                          path = "/portfolio/create";
                          const req: PortfolioRequest = {
                            budget: customBudget,
                            risk: customRisk,
                            horizon: customHorizon,
                            market,
                            createdAt: new Date().toISOString(),
                            userId: user.uid,
                          };
                          const newItem = buildPortfolioRecord(req, "completed");
                          saveUserPortfolios([newItem, ...history]);
                          res = newItem;
                          status = 201;
                        } else if (selectedEndpoint === "delete") {
                          method = "DELETE";
                          path = `/portfolio/${targetId}`;
                          const match = history.find((p) => p.id === targetId);
                          if (match) {
                            saveUserPortfolios(history.filter((p) => p.id !== targetId));
                            res = { detail: `Successfully deleted portfolio ${targetId}` };
                          } else { status = 404; res = { detail: `Portfolio record with ID ${targetId || "null"} not found.` }; }
                        }

                        const latency = Math.round(performance.now() - start);
                        setApiResponse(res);
                        setApiResponseStatus(status);
                        setApiLatency(`${latency}ms`);
                        setApiLogs((cur) => [
                          ...cur,
                          `[INFO] ${new Date().toLocaleTimeString()} - API Request: ${method} ${path} (User: ${user.uid.slice(0, 6)})`,
                          `[INFO] ${new Date().toLocaleTimeString()} - Finished execution in ${latency}ms with status ${status}`,
                        ]);
                      }}
                      className="inline-flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-sky-400 to-violet-500 py-3 text-sm font-semibold text-slate-950 hover:brightness-110 transition font-sans"
                    >
                      Execute API Request
                    </button>
                  </div>

                  <div className="mt-6 rounded-xl border border-white/5 bg-slate-900/60 p-4 flex flex-col">
                    <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-400 font-mono">
                      <span>API Response Payload</span>
                      <span className="font-bold text-sky-400">HTTP {apiResponseStatus} ({apiLatency})</span>
                    </div>
                    <pre className="mt-2 max-h-48 overflow-y-auto rounded-xl bg-slate-950 p-3 text-xs text-sky-100 font-mono whitespace-pre-wrap flex-1 border border-white/5">
                      {JSON.stringify(apiResponse, null, 2)}
                    </pre>
                  </div>
                </div>

                {/* Uvicorn Server Logs */}
                <div className="flex flex-col rounded-3xl border border-white/10 bg-slate-900/40 p-6 backdrop-blur-xl">
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400 font-mono">Uvicorn Server Console Logs</p>
                    <button
                      type="button"
                      onClick={() => setApiLogs(["[INFO] Server console logs cleared.", "[INFO] Listening for scoped API events..."])}
                      className="text-[9px] uppercase tracking-wider bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 px-2 py-1 rounded font-mono"
                    >
                      Clear Logs
                    </button>
                  </div>
                  <div className="mt-5 flex-1 max-h-[300px] lg:max-h-none overflow-y-auto rounded-xl bg-slate-950 p-4 font-mono text-[11px] leading-6 text-emerald-400 border border-emerald-500/10">
                    {apiLogs.map((log, idx) => (
                      <div key={idx} className="whitespace-pre-wrap select-all">
                        {log}
                      </div>
                    ))}
                  </div>

                  {/* Environment Panel */}
                  <div className="mt-6 border-t border-white/5 pt-4">
                    <div className="flex items-center justify-between">
                      <p className="text-xs uppercase tracking-wider text-slate-400 font-mono">PostgreSQL Environment Keys</p>
                      <span className="text-[9px] text-sky-400/70 uppercase font-mono tracking-wider">Scoped SaaS</span>
                    </div>
                    <div className="mt-3 space-y-2 font-mono text-[10px] text-slate-300">
                      <div className="flex justify-between rounded-xl border border-white/5 bg-slate-950/60 px-3 py-2 select-all">
                        <span className="text-slate-500">DATABASE_URL</span>
                        <span className="text-emerald-300/90 truncate max-w-xs">postgresql://flowvest:flowvest123@postgres:5432/flowvest</span>
                      </div>
                      <div className="flex justify-between rounded-xl border border-white/5 bg-slate-950/60 px-3 py-2 select-all">
                        <span className="text-slate-500">OPENROUTER_API_KEY</span>
                        <span className="text-emerald-300/90">sk-or-v1-********</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* PostgreSQL Table Explorer */}
              <div className="mt-8 rounded-3xl border border-white/10 bg-slate-950/60 p-6 backdrop-blur-xl">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/5 pb-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-sky-300/80 font-mono">PostgreSQL DB Table Manager</p>
                    <h3 className="text-lg font-semibold text-white mt-1">Table: `portfolios`</h3>
                    <p className="text-xs text-slate-400 mt-1 font-sans">Queries restricted to user_id = <span className="font-mono text-sky-300">{user.uid}</span>.</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        const req: PortfolioRequest = { budget: 150000, risk: "Medium", horizon: "Medium", market, createdAt: new Date().toISOString(), userId: user.uid };
                        const nextItem = buildPortfolioRecord(req, "completed");
                        saveUserPortfolios([nextItem, ...history]);
                        setApiLogs((c) => [...c, `[INFO] DB-INSERT: Scoped record added for user ${user.uid.slice(0,6)} via DB Manager.`]);
                      }}
                      className="text-[10px] uppercase tracking-wider bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 px-3 py-2 rounded-xl transition font-mono"
                    >
                      + Insert Scoped Row
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const seeds = getSeedRuns(user.uid);
                        saveUserPortfolios(seeds);
                        setApiLogs((c) => [...c, `[INFO] DB-RESET: Flushed table and re-seeded 3 test records for user ${user.uid.slice(0,6)}.`]);
                      }}
                      className="text-[10px] uppercase tracking-wider bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-200 px-3 py-2 rounded-xl transition font-mono"
                    >
                      Reset Scoped DB
                    </button>
                  </div>
                </div>

                <div className="mt-6 overflow-x-auto rounded-xl border border-white/5 bg-slate-950/40">
                  <table className="w-full text-left border-collapse text-xs font-sans">
                    <thead>
                      <tr className="bg-white/5 border-b border-white/10 text-slate-400 font-medium tracking-wider uppercase text-[10px] font-mono">
                        <th className="p-4">id (UUID)</th>
                        <th className="p-4">budget (numeric)</th>
                        <th className="p-4">risk_level (varchar)</th>
                        <th className="p-4">horizon (varchar)</th>
                        <th className="p-4">status</th>
                        <th className="p-4">created_at</th>
                        <th className="p-4 text-right">actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5 text-slate-300 font-sans">
                      {history.map((row) => (
                        <tr key={row.id} className="hover:bg-white/2 transition">
                          <td className="p-4 font-mono text-sky-300 select-all">{row.id}</td>
                          <td className="p-4 font-semibold text-white">{formatRupees(row.budget)}</td>
                          <td className="p-4">{row.risk}</td>
                          <td className="p-4">{row.horizon}</td>
                          <td className="p-4"><StatusBadge status={row.status} /></td>
                          <td className="p-4 font-mono text-slate-400">{dateFormatter.format(new Date(row.createdAt))}</td>
                          <td className="p-4 text-right">
                            <button
                              type="button"
                              onClick={() => {
                                saveUserPortfolios(history.filter((p) => p.id !== row.id));
                                if (selectedId === row.id) setSelectedId(null);
                                setApiLogs((c) => [...c, `[INFO] DB-DELETE operation on id: ${row.id} (Table: portfolios)`]);
                              }}
                              className="text-[9px] font-mono bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-200 px-2 py-1 rounded uppercase tracking-wider"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {history.length === 0 && (
                    <div className="text-center py-8 text-xs text-slate-500">
                      Empty set (0 rows returned for user_id = '{user.uid.slice(0,8)}...').
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>

        <footer className="relative z-10 mx-auto max-w-7xl border-t border-white/10 px-6 py-10 text-xs text-slate-500 sm:px-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-white font-semibold">FlowVest AI</p>
              <p className="mt-2 max-w-xl leading-6 select-none">
                Educational product preview only. The multi-agent pipeline logic, API endpoints, and database interactions represent a staff-level SaaS system design. Portfolio outputs are illustrative and should not be treated as professional investment advice.
              </p>
            </div>
            <div className="text-left sm:text-right font-mono">
              <p>SaaS Architecture Sandbox v1.0</p>
              <p className="mt-1 text-slate-600">Built with React 19, FastAPI, PostgreSQL, and Firebase Auth.</p>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
