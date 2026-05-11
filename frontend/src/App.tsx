import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Database,
  FileJson,
  LayoutDashboard,
  Play,
  RefreshCw,
  Settings,
  Table as TableIcon,
} from "lucide-react";
import {
  fetchHealth,
  fetchMetadata,
  fetchSummary,
  getJobStatus,
  listJobs,
  startExtraction,
} from "./api.ts";
import type {
  BackendJobRecord,
  ExtractionPayload,
  SummaryRow,
} from "./types.ts";

type ApiState = "idle" | "loading" | "ok" | "error";

type JobRecord = BackendJobRecord & {
  id: string;
};

type ExtractFormState = {
  minLon: string;
  minLat: string;
  maxLon: string;
  maxLat: string;
  date: string;
  locationName: string;
  runFetch: boolean;
  fetchOnly: boolean;
  downloadScene: boolean;
  annotateShips: boolean;
  cloudFilterPct: string;
  ndwiThreshold: string;
  tileSize: string;
  stride: string;
  blackThreshold: string;
  blurThreshold: string;
  shipMinAreaPx: string;
  shipMaxAreaPx: string;
  shipMinIntensity: string;
  shipThresholdPercentile: string;
};

const DEFAULT_FORM: ExtractFormState = {
  minLon: "72.80",
  minLat: "18.87",
  maxLon: "72.97",
  maxLat: "18.98",
  date: "2024-02-15",
  locationName: "mumbai",
  runFetch: false,
  fetchOnly: false,
  downloadScene: true,
  annotateShips: true,
  cloudFilterPct: "20",
  ndwiThreshold: "0",
  tileSize: "256",
  stride: "204",
  blackThreshold: "0.8",
  blurThreshold: "50",
  shipMinAreaPx: "2",
  shipMaxAreaPx: "600",
  shipMinIntensity: "130",
  shipThresholdPercentile: "99.5",
};

function prettyTime(value?: string): string {
  if (!value) {
    return "N/A";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function parseNumber(value: string, fieldName: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${fieldName} must be a valid number.`);
  }
  return parsed;
}

function getStatusBadge(status?: string) {
  switch (status) {
    case "complete":
      return (
        <span className="status-badge status-badge-complete">
          <CheckCircle2 className="w-3 h-3 mr-1" /> Complete
        </span>
      );
    case "failed":
      return (
        <span className="status-badge status-badge-failed">
          <AlertCircle className="w-3 h-3 mr-1" /> Failed
        </span>
      );
    case "running":
      return (
        <span className="status-badge status-badge-running">
          <Activity className="w-3 h-3 mr-1" /> Running
        </span>
      );
    default:
      return (
        <span className="status-badge status-badge-queued">
          <Clock className="w-3 h-3 mr-1" /> Queued
        </span>
      );
  }
}

export default function App() {
  const [form, setForm] = useState<ExtractFormState>(DEFAULT_FORM);

  const [healthState, setHealthState] = useState<ApiState>("idle");
  const [healthMessage, setHealthMessage] = useState<string>("Unknown");

  const [extractState, setExtractState] = useState<ApiState>("idle");
  const [extractMessage, setExtractMessage] = useState<string>("");
  const [activeJobId, setActiveJobId] = useState<string>("");

  const [jobsState, setJobsState] = useState<ApiState>("idle");
  const [jobsError, setJobsError] = useState<string>("");
  const [jobs, setJobs] = useState<JobRecord[]>([]);

  const [metadataState, setMetadataState] = useState<ApiState>("idle");
  const [metadataPath, setMetadataPath] = useState<string>("");
  const [metadataContent, setMetadataContent] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [metadataError, setMetadataError] = useState<string>("");

  const [summaryState, setSummaryState] = useState<ApiState>("idle");
  const [summaryPath, setSummaryPath] = useState<string>("");
  const [summaryRows, setSummaryRows] = useState<SummaryRow[]>([]);
  const [summaryError, setSummaryError] = useState<string>("");

  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  const activeJob = useMemo(
    () => jobs.find((job) => job.id === activeJobId),
    [jobs, activeJobId],
  );

  const summaryColumns = useMemo(() => {
    if (summaryRows.length === 0) {
      return [];
    }
    return Object.keys(summaryRows[0]);
  }, [summaryRows]);

  const refreshJobs = useCallback(async () => {
    setJobsState("loading");
    setJobsError("");

    try {
      const payload = await listJobs();
      const records = Object.entries(payload)
        .map(([id, job]) => ({ id, ...job }))
        .sort((a, b) => {
          const left = Date.parse(a.created_at ?? "");
          const right = Date.parse(b.created_at ?? "");
          if (Number.isNaN(left) && Number.isNaN(right)) {
            return 0;
          }
          if (Number.isNaN(left)) {
            return 1;
          }
          if (Number.isNaN(right)) {
            return -1;
          }
          return right - left;
        });

      setJobs(records);
      setJobsState("ok");
    } catch (error) {
      setJobsState("error");
      setJobsError(
        error instanceof Error ? error.message : "Unable to load jobs.",
      );
    }
  }, []);

  const refreshMetadata = useCallback(async () => {
    setMetadataState("loading");
    setMetadataError("");

    try {
      const payload = await fetchMetadata();
      setMetadataPath(payload.path);
      setMetadataContent(payload.content);
      setMetadataState("ok");
    } catch (error) {
      setMetadataState("error");
      setMetadataError(
        error instanceof Error
          ? error.message
          : "Unable to load metadata.json.",
      );
    }
  }, []);

  const refreshSummary = useCallback(async () => {
    setSummaryState("loading");
    setSummaryError("");

    try {
      const payload = await fetchSummary();
      setSummaryPath(payload.path);
      setSummaryRows(payload.content);
      setSummaryState("ok");
    } catch (error) {
      setSummaryState("error");
      setSummaryError(
        error instanceof Error
          ? error.message
          : "Unable to load dataset_summary.csv.",
      );
    }
  }, []);

  const checkHealth = useCallback(async () => {
    setHealthState("loading");
    setHealthMessage("Checking backend health...");

    try {
      const payload = await fetchHealth();
      setHealthState("ok");
      setHealthMessage(
        payload.status === "ok" ? "Backend online" : payload.status,
      );
    } catch (error) {
      setHealthState("error");
      setHealthMessage(
        error instanceof Error ? error.message : "Backend unavailable",
      );
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void checkHealth();
      void refreshJobs();
      void refreshMetadata();
      void refreshSummary();
    });
  }, [checkHealth, refreshJobs, refreshMetadata, refreshSummary]);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const latest = await getJobStatus(activeJobId);
        if (cancelled) {
          return;
        }

        setJobs((previousJobs) => {
          const nextJobs = [...previousJobs];
          const index = nextJobs.findIndex((job) => job.id === activeJobId);

          if (index >= 0) {
            nextJobs[index] = { id: activeJobId, ...latest };
            return nextJobs;
          }

          return [{ id: activeJobId, ...latest }, ...nextJobs];
        });

        if (latest.status === "complete" || latest.status === "failed") {
          setActiveJobId("");
          setExtractState(latest.status === "complete" ? "ok" : "error");
          setExtractMessage(
            latest.status === "complete"
              ? "Extraction finished successfully."
              : (latest.error ?? "Extraction failed."),
          );

          if (latest.status === "complete") {
            void refreshMetadata();
            void refreshSummary();
          }
        }
      } catch {
        // Keep polling; transient network issues should not cancel monitoring.
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeJobId, refreshMetadata, refreshSummary]);

  const updateFormField = (
    field: keyof ExtractFormState,
    value: string | boolean,
  ): void => {
    setForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const buildPayload = (): ExtractionPayload => {
    const minLon = parseNumber(form.minLon, "Minimum longitude");
    const minLat = parseNumber(form.minLat, "Minimum latitude");
    const maxLon = parseNumber(form.maxLon, "Maximum longitude");
    const maxLat = parseNumber(form.maxLat, "Maximum latitude");

    if (minLon >= maxLon || minLat >= maxLat) {
      throw new Error(
        "Bounding box must satisfy min < max for both longitude and latitude.",
      );
    }

    if (!form.locationName.trim()) {
      throw new Error("Location name is required.");
    }

    if (!form.date.trim()) {
      throw new Error("Date is required.");
    }

    return {
      bbox: [minLon, minLat, maxLon, maxLat],
      date: form.date,
      location_name: form.locationName.trim(),
      run_fetch: form.runFetch,
      fetch_only: form.fetchOnly,
      download_scene: form.downloadScene,
      annotate_ships: form.annotateShips,
      cloud_filter_pct: parseNumber(
        form.cloudFilterPct,
        "Cloud filter percent",
      ),
      ndwi_threshold: parseNumber(form.ndwiThreshold, "NDWI threshold"),
      tile_size: parseNumber(form.tileSize, "Tile size"),
      stride: parseNumber(form.stride, "Stride"),
      black_threshold: parseNumber(form.blackThreshold, "Black threshold"),
      blur_threshold: parseNumber(form.blurThreshold, "Blur threshold"),
      ship_min_area_px: parseNumber(form.shipMinAreaPx, "Ship minimum area"),
      ship_max_area_px: parseNumber(form.shipMaxAreaPx, "Ship maximum area"),
      ship_min_intensity: parseNumber(
        form.shipMinIntensity,
        "Ship minimum intensity",
      ),
      ship_threshold_percentile: parseNumber(
        form.shipThresholdPercentile,
        "Ship threshold percentile",
      ),
    };
  };

  const handleExtractSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    setExtractState("loading");
    setExtractMessage("Submitting extraction request...");

    try {
      const payload = buildPayload();
      const response = await startExtraction(payload);
      setActiveJobId(response.job_id);
      setExtractState("ok");
      setExtractMessage(`Queued job ${response.job_id}`);
      await refreshJobs();
    } catch (error) {
      setExtractState("error");
      setExtractMessage(
        error instanceof Error ? error.message : "Failed to submit extraction.",
      );
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-700">
      {/* Hero Section */}
      <header className="glass-panel p-8 md:p-10 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -mr-32 -mt-32 transition-transform duration-1000 group-hover:scale-110" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl -ml-32 -mb-32 transition-transform duration-1000 group-hover:scale-110" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-4 max-w-3xl">
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold uppercase tracking-widest border border-emerald-100">
              <Database className="w-3 h-3 mr-2" /> CV-Lab-EL Control Deck
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 leading-tight">
              Ship Dataset{" "}
              <span className="text-transparent bg-clip-text bg-linear-to-r from-emerald-600 to-blue-600">
                Extraction
              </span>
            </h1>
            <p className="text-lg text-slate-600 font-medium leading-relaxed">
              Launch high-fidelity extraction jobs, monitor real-time processing
              phases, and inspect generated metadata from a centralized
              operational dashboard.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => void checkHealth()}
              className="p-3 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-sm active:scale-95"
              title="Refresh Backend Health"
            >
              <RefreshCw
                className={`w-5 h-5 ${healthState === "loading" ? "animate-spin text-emerald-600" : ""}`}
              />
            </button>
            <div
              className={`px-4 py-2.5 rounded-xl border flex items-center gap-2 shadow-sm ${
                healthState === "ok"
                  ? "bg-emerald-50 border-emerald-100 text-emerald-700"
                  : healthState === "error"
                    ? "bg-rose-50 border-rose-100 text-rose-700"
                    : "bg-slate-50 border-slate-200 text-slate-600"
              }`}
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  healthState === "ok"
                    ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse"
                    : healthState === "error"
                      ? "bg-rose-500"
                      : "bg-slate-400"
                }`}
              />
              <span className="text-sm font-bold uppercase tracking-wider">
                {healthMessage}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <main className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Extraction Form */}
        <section className="glass-panel overflow-hidden flex flex-col">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
            <div className="p-2 bg-emerald-600 rounded-lg text-white">
              <Play className="w-5 h-5 fill-current" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                New Extraction
              </h2>
              <p className="text-sm text-slate-500">
                Configure spatial and temporal parameters
              </p>
            </div>
          </div>

          <form
            onSubmit={(event) => void handleExtractSubmit(event)}
            className="p-6 space-y-6 flex-1"
          >
            {/* Bounding Box */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <LayoutDashboard className="w-3 h-3" /> Spatial Bounding Box
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Min Lon", field: "minLon" },
                  { label: "Min Lat", field: "minLat" },
                  { label: "Max Lon", field: "maxLon" },
                  { label: "Max Lat", field: "maxLat" },
                ].map((item) => (
                  <div key={item.field} className="space-y-1">
                    <span className="text-[10px] font-semibold text-slate-400 ml-1">
                      {item.label}
                    </span>
                    <input
                      type="number"
                      step="any"
                      value={
                        form[item.field as keyof ExtractFormState] as string
                      }
                      onChange={(event) =>
                        updateFormField(
                          item.field as keyof ExtractFormState,
                          event.target.value,
                        )
                      }
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all outline-none"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Date Selection
                </label>
                <input
                  type="date"
                  value={form.date}
                  onChange={(event) =>
                    updateFormField("date", event.target.value)
                  }
                  className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Location Name
                </label>
                <input
                  type="text"
                  value={form.locationName}
                  onChange={(event) =>
                    updateFormField("locationName", event.target.value)
                  }
                  placeholder="e.g. Mumbai Port"
                  className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all outline-none"
                />
              </div>
            </div>

            {/* Toggles */}
            <div className="bg-slate-50 rounded-2xl p-4 space-y-3 border border-slate-100">
              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={form.runFetch}
                    onChange={(event) =>
                      updateFormField("runFetch", event.target.checked)
                    }
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-emerald-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-transform peer-checked:after:translate-x-5 shadow-sm" />
                </div>
                <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors">
                  Run Fetch Phase (GEE Export)
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={form.fetchOnly}
                    onChange={(event) =>
                      updateFormField("fetchOnly", event.target.checked)
                    }
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-blue-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-transform peer-checked:after:translate-x-5 shadow-sm" />
                </div>
                <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors">
                  Fetch Only (Skip Local Processing)
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={form.downloadScene}
                    onChange={(event) =>
                      updateFormField("downloadScene", event.target.checked)
                    }
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-cyan-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-transform peer-checked:after:translate-x-5 shadow-sm" />
                </div>
                <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors">
                  Direct Download Scene
                </span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={form.annotateShips}
                    onChange={(event) =>
                      updateFormField("annotateShips", event.target.checked)
                    }
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 rounded-full peer peer-checked:bg-amber-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-transform peer-checked:after:translate-x-5 shadow-sm" />
                </div>
                <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition-colors">
                  Generate Ship Candidate Labels
                </span>
              </label>
            </div>

            {/* Advanced Controls */}
            <div className="space-y-4">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-sm font-bold text-slate-400 hover:text-emerald-600 transition-colors"
              >
                <Settings
                  className={`w-4 h-4 transition-transform duration-300 ${showAdvanced ? "rotate-90 text-emerald-600" : ""}`}
                />
                {showAdvanced ? "Hide Advanced Tuning" : "Show Advanced Tuning"}
                {showAdvanced ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>

              {showAdvanced && (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-4 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200 animate-in slide-in-from-top-2 duration-300">
                  {[
                    { label: "Cloud Filter %", field: "cloudFilterPct" },
                    { label: "NDWI Threshold", field: "ndwiThreshold" },
                    { label: "Tile Size", field: "tileSize" },
                    { label: "Stride", field: "stride" },
                    { label: "Black Threshold", field: "blackThreshold" },
                    { label: "Blur Threshold", field: "blurThreshold" },
                    { label: "Ship Min Area", field: "shipMinAreaPx" },
                    { label: "Ship Max Area", field: "shipMaxAreaPx" },
                    { label: "Ship Min Bright", field: "shipMinIntensity" },
                    {
                      label: "Ship Percentile",
                      field: "shipThresholdPercentile",
                    },
                  ].map((item) => (
                    <div key={item.field} className="space-y-1">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">
                        {item.label}
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={
                          form[item.field as keyof ExtractFormState] as string
                        }
                        onChange={(event) =>
                          updateFormField(
                            item.field as keyof ExtractFormState,
                            event.target.value,
                          )
                        }
                        className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:ring-2 focus:ring-emerald-500/20 outline-none"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={extractState === "loading"}
                className="w-full py-4 bg-linear-to-r from-emerald-600 to-blue-600 hover:from-emerald-700 hover:to-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-emerald-600/20 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-lg"
              >
                {extractState === "loading" ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Start Extraction
                  </>
                )}
              </button>
              {extractMessage && (
                <div
                  className={`mt-4 p-3 rounded-xl text-sm font-medium flex items-center gap-2 ${
                    extractState === "error"
                      ? "bg-rose-50 text-rose-700 border border-rose-100"
                      : "bg-emerald-50 text-emerald-700 border border-emerald-100"
                  }`}
                >
                  {extractState === "error" ? (
                    <AlertCircle className="w-4 h-4 shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                  )}
                  {extractMessage}
                </div>
              )}
            </div>
          </form>
        </section>

        {/* Job Monitor */}
        <section className="glass-panel overflow-hidden flex flex-col max-h-212.5">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg text-white">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">
                  Job Monitor
                </h2>
                <p className="text-sm text-slate-500">
                  Real-time status updates
                </p>
              </div>
            </div>
            <button
              onClick={() => void refreshJobs()}
              className="text-xs font-bold text-slate-400 hover:text-blue-600 transition-colors uppercase tracking-widest flex items-center gap-2"
            >
              <RefreshCw
                className={`w-3 h-3 ${jobsState === "loading" ? "animate-spin" : ""}`}
              />{" "}
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
            {jobsState === "error" && (
              <div className="p-4 bg-rose-50 text-rose-700 border border-rose-100 rounded-2xl flex items-center gap-3">
                <AlertCircle className="w-5 h-5" />
                <span className="text-sm font-medium">{jobsError}</span>
              </div>
            )}

            {jobs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-4 py-20 opacity-40">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
                  <Clock className="w-8 h-8 text-slate-400" />
                </div>
                <p className="text-slate-500 font-medium italic">
                  No extraction jobs found.
                  <br />
                  Submit a request to see it here.
                </p>
              </div>
            ) : (
              jobs.map((job) => (
                <article
                  key={job.id}
                  className={`group p-4 rounded-2xl border transition-all duration-300 ${
                    activeJobId === job.id
                      ? "bg-emerald-50/50 border-emerald-200 ring-2 ring-emerald-500/10"
                      : "bg-white border-slate-100 hover:border-slate-300 hover:shadow-md"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-1.5 rounded-lg border ${
                          job.status === "complete"
                            ? "bg-emerald-50 border-emerald-100 text-emerald-600"
                            : job.status === "failed"
                              ? "bg-rose-50 border-rose-100 text-rose-600"
                              : "bg-slate-50 border-slate-100 text-slate-400"
                        }`}
                      >
                        <Database className="w-4 h-4" />
                      </div>
                      <code className="text-xs font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md group-hover:bg-slate-200 transition-colors">
                        {job.id.substring(0, 8)}...
                      </code>
                    </div>
                    {getStatusBadge(job.status)}
                  </div>

                  <div className="grid grid-cols-2 gap-y-3 gap-x-6 text-[11px]">
                    <div className="space-y-0.5">
                      <p className="text-slate-400 uppercase font-bold tracking-tighter">
                        Location
                      </p>
                      <p className="text-slate-700 font-semibold truncate">
                        {job.location ?? "N/A"}
                      </p>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-slate-400 uppercase font-bold tracking-tighter">
                        Target Date
                      </p>
                      <p className="text-slate-700 font-semibold">
                        {job.date ?? "N/A"}
                      </p>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-slate-400 uppercase font-bold tracking-tighter">
                        Started At
                      </p>
                      <p className="text-slate-700 font-semibold">
                        {prettyTime(job.started_at)}
                      </p>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-slate-400 uppercase font-bold tracking-tighter">
                        Finished At
                      </p>
                      <p className="text-slate-700 font-semibold">
                        {prettyTime(job.finished_at)}
                      </p>
                    </div>
                  </div>

                  {job.error && (
                    <div className="mt-4 p-3 bg-rose-50 border border-rose-100 rounded-xl text-xs text-rose-700 font-medium flex items-start gap-2">
                      <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{job.error}</span>
                    </div>
                  )}

                  {job.result && (
                    <details className="mt-4 group/details">
                      <summary className="text-[11px] font-bold text-slate-400 hover:text-slate-600 cursor-pointer list-none flex items-center gap-1 uppercase tracking-widest">
                        <ChevronDown className="w-3 h-3 group-open/details:rotate-180 transition-transform" />
                        View Results JSON
                      </summary>
                      <div className="mt-2 p-3 bg-slate-900 rounded-xl text-[10px] text-emerald-400 font-mono overflow-x-auto border border-slate-800">
                        <pre>{JSON.stringify(job.result, null, 2)}</pre>
                      </div>
                    </details>
                  )}
                </article>
              ))
            )}
          </div>

          {activeJob && (
            <div className="px-6 py-3 bg-emerald-600 text-white text-[11px] font-bold uppercase tracking-[0.2em] animate-pulse text-center">
              Tracking Job: {activeJob.id}
            </div>
          )}
        </section>

        {/* Metadata Viewer */}
        <section className="glass-panel overflow-hidden flex flex-col max-h-150">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-600 rounded-lg text-white">
                <FileJson className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Metadata</h2>
                <p className="text-sm text-slate-500">
                  Latest generated configuration
                </p>
              </div>
            </div>
            <button
              onClick={() => void refreshMetadata()}
              className="text-xs font-bold text-slate-400 hover:text-purple-600 transition-colors uppercase tracking-widest flex items-center gap-2"
            >
              <RefreshCw
                className={`w-3 h-3 ${metadataState === "loading" ? "animate-spin" : ""}`}
              />{" "}
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-hidden flex flex-col p-6 space-y-4">
            <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 overflow-x-auto whitespace-nowrap">
              <Database className="w-3 h-3" />{" "}
              {metadataPath || "No metadata loaded"}
            </div>

            {metadataState === "error" && (
              <div className="p-4 bg-rose-50 text-rose-700 border border-rose-100 rounded-2xl text-sm font-medium italic">
                {metadataError}
              </div>
            )}

            <div className="flex-1 bg-slate-900 rounded-2xl p-4 overflow-auto border border-slate-800 relative group">
              <div className="absolute top-4 right-4 text-[10px] font-bold text-slate-600 uppercase tracking-widest opacity-50 group-hover:opacity-100 transition-opacity">
                JSON Viewer
              </div>
              {metadataContent ? (
                <pre className="text-[11px] leading-relaxed font-mono text-purple-300">
                  {JSON.stringify(metadataContent, null, 2)}
                </pre>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-600 italic text-sm">
                  Waiting for data...
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Summary Table */}
        <section className="glass-panel overflow-hidden flex flex-col lg:col-span-2">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-600 rounded-lg text-white">
                <TableIcon className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">
                  Dataset Summary
                </h2>
                <p className="text-sm text-slate-500">
                  Tabular inspection of extraction outputs
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-[10px] font-mono text-slate-400 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 max-w-xs truncate hidden md:block">
                {summaryPath || "No summary loaded"}
              </div>
              <button
                onClick={() => void refreshSummary()}
                className="shrink-0 text-xs font-bold text-slate-400 hover:text-amber-600 transition-colors uppercase tracking-widest flex items-center gap-2 border border-slate-200 px-4 py-2 rounded-xl bg-white hover:border-amber-200 shadow-sm"
              >
                <RefreshCw
                  className={`w-3 h-3 ${summaryState === "loading" ? "animate-spin" : ""}`}
                />{" "}
                Refresh Table
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto min-h-100 custom-scrollbar">
            {summaryState === "error" && (
              <div className="m-6 p-4 bg-rose-50 text-rose-700 border border-rose-100 rounded-2xl text-sm italic">
                {summaryError}
              </div>
            )}

            {summaryRows.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-400 italic text-sm">
                No data rows available to display.
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 sticky top-0 z-20">
                    {summaryColumns.map((column) => (
                      <th
                        key={column}
                        className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider whitespace-nowrap"
                      >
                        {column.replace(/_/g, " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {summaryRows.slice(0, 100).map((row, index) => (
                    <tr
                      key={`${index}-${row[summaryColumns[0]]}`}
                      className="hover:bg-slate-50/80 transition-colors"
                    >
                      {summaryColumns.map((column) => (
                        <td
                          key={`${index}-${column}`}
                          className="px-6 py-4 text-xs text-slate-600 whitespace-nowrap font-medium"
                        >
                          {column === "status"
                            ? getStatusBadge(row[column] as string)
                            : String(row[column] ?? "-")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/30 text-[10px] font-bold text-slate-400 uppercase tracking-widest flex justify-between">
            <span>Showing top {Math.min(summaryRows.length, 100)} records</span>
            <span>Total: {summaryRows.length} items</span>
          </div>
        </section>
      </main>

      <footer className="text-center py-10 space-y-2 opacity-50">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.3em]">
          Operational Environment v1.0.4
        </p>
        <p className="text-xs text-slate-400">
          © 2026 CV-Lab-EL Systems. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
