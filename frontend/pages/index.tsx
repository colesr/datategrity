import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Project {
  id: number;
  name: string;
  description: string;
  dataset_filename?: string;
}

interface DatasetPreview {
  rows: number;
  columns: number;
  column_names: string[];
  data_types: Record<string, string>;
  preview: Record<string, any>[];
  memory_mb: number;
}

interface AnalysisHistoryItem {
  id: number;
  project_id: number;
  operation_type: string;
  parameters: string;
  results: string | null;
  created_at: string;
}

export default function Home() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDescription, setNewProjectDescription] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [output, setOutput] = useState<any>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);
  const [analysisColumns, setAnalysisColumns] = useState("");
  const [anomalyColumn, setAnomalyColumn] = useState("");
  const [anomalyMethod, setAnomalyMethod] = useState("zscore");
  const [rules, setRules] = useState("id:unique");
  const [operations, setOperations] = useState("name:lowercase");
  const [reportType, setReportType] = useState("Quality Report");
  const [activeTab, setActiveTab] = useState("project");

  useEffect(() => {
    if (token) {
      fetchProjects();
    }
  }, [token]);

  useEffect(() => {
    if (selectedProjectId && token) {
      loadPreview();
      loadHistory();
    }
  }, [selectedProjectId]);

  const request = async (path: string, options: RequestInit = {}) => {
    const headers: HeadersInit = { ...(options.headers || {}), "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || response.statusText);
    }
    return response.json();
  };

  const registerUser = async () => {
    try {
      await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      setStatus("Registered successfully. Please log in.");
    } catch (err) {
      setStatus(`Register failed: ${err}`);
    }
  };

  const loginUser = async () => {
    try {
      const result = await request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(result.access_token);
      setStatus("Logged in successfully.");
    } catch (err) {
      setStatus(`Login failed: ${err}`);
    }
  };

  const fetchProjects = async () => {
    try {
      const list = await request("/projects");
      setProjects(list);
      if (!selectedProjectId && list.length) {
        setSelectedProjectId(list[0].id);
      }
    } catch (err) {
      setStatus(`Failed to load projects: ${err}`);
    }
  };

  const createProject = async () => {
    try {
      const project = await request("/projects", {
        method: "POST",
        body: JSON.stringify({ name: newProjectName, description: newProjectDescription }),
      });
      setProjects((prev) => [...prev, project]);
      setSelectedProjectId(project.id);
      setNewProjectName("");
      setNewProjectDescription("");
      setStatus("Project created.");
    } catch (err) {
      setStatus(`Create project failed: ${err}`);
    }
  };

  const uploadDataset = async () => {
    if (!selectedProjectId || !uploadFile) {
      setStatus("Choose a project and a dataset file first.");
      return;
    }
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      const response = await fetch(`${API_BASE}/projects/${selectedProjectId}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      setStatus(result.message);
      setUploadFile(null);
      fetchProjects();
      loadPreview();
    } catch (err) {
      setStatus(`Upload failed: ${err}`);
    }
  };

  const loadPreview = async () => {
    if (!selectedProjectId) return;
    try {
      const data = await request(`/projects/${selectedProjectId}/preview`);
      setPreview(data);
    } catch (err) {
      setPreview(null);
    }
  };

  const loadHistory = async () => {
    if (!selectedProjectId) return;
    try {
      const data = await request(`/projects/${selectedProjectId}/history`);
      setHistory(data.items);
    } catch (err) {
      setHistory([]);
    }
  };

  const runAnalysis = async () => {
    if (!selectedProjectId) return;
    try {
      const body = analysisColumns ? { columns: analysisColumns.split(",").map((value) => value.trim()) } : {};
      const result = await request(`/projects/${selectedProjectId}/analyze`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setOutput(result);
      setStatus("Analysis complete.");
      loadHistory();
    } catch (err) {
      setStatus(`Analyze failed: ${err}`);
    }
  };

  const runAnomalyDetection = async () => {
    if (!selectedProjectId) return;
    try {
      const result = await request(`/projects/${selectedProjectId}/anomalies`, {
        method: "POST",
        body: JSON.stringify({ column: anomalyColumn, method: anomalyMethod }),
      });
      setOutput(result);
      setStatus("Anomaly detection complete.");
      loadHistory();
    } catch (err) {
      setStatus(`Anomaly detection failed: ${err}`);
    }
  };

  const validateData = async () => {
    if (!selectedProjectId) return;
    try {
      const result = await request(`/projects/${selectedProjectId}/validate`, {
        method: "POST",
        body: JSON.stringify({ rules }),
      });
      setOutput(result);
      setStatus("Validation complete.");
      loadHistory();
    } catch (err) {
      setStatus(`Validation failed: ${err}`);
    }
  };

  const cleanData = async () => {
    if (!selectedProjectId) return;
    try {
      const result = await request(`/projects/${selectedProjectId}/clean`, {
        method: "POST",
        body: JSON.stringify({ operations }),
      });
      setOutput(result);
      setStatus("Cleaning complete.");
      loadHistory();
    } catch (err) {
      setStatus(`Cleaning failed: ${err}`);
    }
  };

  const generateReport = async () => {
    if (!selectedProjectId) return;
    try {
      const result = await request(`/projects/${selectedProjectId}/report`, {
        method: "POST",
        body: JSON.stringify({ report_type: reportType }),
      });
      setOutput(result);
      setStatus("Report generated.");
      loadHistory();
    } catch (err) {
      setStatus(`Report failed: ${err}`);
    }
  };

  const restoreFromHistory = (item: AnalysisHistoryItem) => {
    try {
      const params = JSON.parse(item.parameters);
      const results = item.results ? JSON.parse(item.results) : null;
      
      switch (item.operation_type) {
        case "analyze":
          setAnalysisColumns(params.columns?.join(", ") || "");
          break;
        case "anomaly":
          setAnomalyColumn(params.column || "");
          setAnomalyMethod(params.method || "zscore");
          break;
        case "validate":
          setRules(params.rules || "");
          break;
        case "clean":
          setOperations(params.operations || "");
          break;
      }
      
      if (results) {
        setOutput(results);
      }
      setStatus(`Restored ${item.operation_type} from history (${item.created_at})`);
    } catch (err) {
      setStatus(`Failed to restore: ${err}`);
    }
  };

  return (
    <main className="container">
      <section className="card header">
        <h1>📊 Datategrity</h1>
        <p>An all-in-one platform for data quality, validation, and AI-powered insights with persistent workspaces.</p>
      </section>

      {!token ? (
        <section className="card">
          <h2>Authentication</h2>
          <div className="form-grid">
            <label>
              Username
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter username" />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter password" />
            </label>
          </div>
          <div className="button-row">
            <button onClick={registerUser} className="btn-secondary">Register</button>
            <button onClick={loginUser} className="btn-primary">Login</button>
          </div>
        </section>
      ) : (
        <>
          <section className="card">
            <h2>📁 Projects</h2>
            <div className="form-grid">
              <label>
                Project Name
                <input value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="My Analysis Project" />
              </label>
              <label>
                Description
                <input value={newProjectDescription} onChange={(e) => setNewProjectDescription(e.target.value)} placeholder="Project description" />
              </label>
            </div>
            <button onClick={createProject} className="btn-primary">+ Create Project</button>

            {projects.length > 0 && (
              <div className="project-list">
                <label>
                  Select Project
                  <select value={selectedProjectId ?? undefined} onChange={(e) => setSelectedProjectId(Number(e.target.value))}>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
          </section>

          {selectedProjectId && (
            <>
              <section className="card">
                <h2>📤 Dataset</h2>
                <div className="form-grid">
                  <label>
                    Upload CSV or Excel File
                    <input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} accept=".csv,.xlsx,.xls" />
                  </label>
                </div>
                <button onClick={uploadDataset} className="btn-primary">Upload Dataset</button>
              </section>

              {preview && (
                <section className="card">
                  <h2>📋 Dataset Preview</h2>
                  <div className="preview-info">
                    <div className="info-item">
                      <strong>Rows:</strong> {preview.rows.toLocaleString()}
                    </div>
                    <div className="info-item">
                      <strong>Columns:</strong> {preview.columns}
                    </div>
                    <div className="info-item">
                      <strong>Memory:</strong> {preview.memory_mb} MB
                    </div>
                  </div>
                  
                  <div className="columns-info">
                    <strong>Column Names &amp; Types:</strong>
                    <div className="columns-grid">
                      {preview.column_names.map((col) => (
                        <div key={col} className="column-item">
                          <code>{col}</code>
                          <span className="type-badge">{preview.data_types[col]}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="table-wrapper">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {preview.column_names.map((col) => (
                            <th key={col}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.preview.map((row, idx) => (
                          <tr key={idx}>
                            {preview.column_names.map((col) => (
                              <td key={`${idx}-${col}`}>{String(row[col] ?? "")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              <section className="card">
                <h2>🔧 Analysis Workspace</h2>
                <div className="tabs">
                  <button
                    className={`tab ${activeTab === "analysis" ? "active" : ""}`}
                    onClick={() => setActiveTab("analysis")}
                  >
                    Analysis
                  </button>
                  <button
                    className={`tab ${activeTab === "validation" ? "active" : ""}`}
                    onClick={() => setActiveTab("validation")}
                  >
                    Validation
                  </button>
                  <button
                    className={`tab ${activeTab === "cleaning" ? "active" : ""}`}
                    onClick={() => setActiveTab("cleaning")}
                  >
                    Cleaning
                  </button>
                  <button
                    className={`tab ${activeTab === "reporting" ? "active" : ""}`}
                    onClick={() => setActiveTab("reporting")}
                  >
                    Reporting
                  </button>
                </div>

                {activeTab === "analysis" && (
                  <div className="tab-content">
                    <div className="form-grid">
                      <label>
                        Columns to Analyze
                        <input value={analysisColumns} onChange={(e) => setAnalysisColumns(e.target.value)} placeholder="comma-separated (leave empty for all)" />
                      </label>
                      <button onClick={runAnalysis} className="btn-primary">Analyze Quality</button>
                    </div>

                    <div className="form-grid">
                      <label>
                        Anomaly Column
                        <input value={anomalyColumn} onChange={(e) => setAnomalyColumn(e.target.value)} placeholder="numeric column name" />
                      </label>
                      <label>
                        Method
                        <select value={anomalyMethod} onChange={(e) => setAnomalyMethod(e.target.value)}>
                          <option value="zscore">Z-Score</option>
                          <option value="iqr">IQR</option>
                        </select>
                      </label>
                      <button onClick={runAnomalyDetection} className="btn-primary">Detect Anomalies</button>
                    </div>
                  </div>
                )}

                {activeTab === "validation" && (
                  <div className="tab-content">
                    <label>
                      Validation Rules
                      <textarea rows={4} value={rules} onChange={(e) => setRules(e.target.value)} placeholder="id:unique, price:range:0,1000, email:null" />
                    </label>
                    <button onClick={validateData} className="btn-primary">Validate Data</button>
                  </div>
                )}

                {activeTab === "cleaning" && (
                  <div className="tab-content">
                    <label>
                      Cleaning Operations
                      <textarea rows={4} value={operations} onChange={(e) => setOperations(e.target.value)} placeholder="name:lowercase, price:fill_mean, description:trim" />
                    </label>
                    <button onClick={cleanData} className="btn-primary">Apply Cleaning</button>
                  </div>
                )}

                {activeTab === "reporting" && (
                  <div className="tab-content">
                    <label>
                      Report Type
                      <select value={reportType} onChange={(e) => setReportType(e.target.value)}>
                        <option value="Quality Report">Quality Report</option>
                        <option value="Anomaly Summary">Anomaly Summary</option>
                        <option value="Validation Summary">Validation Summary</option>
                      </select>
                    </label>
                    <button onClick={generateReport} className="btn-primary">Generate Report</button>
                  </div>
                )}
              </section>

              {history.length > 0 && (
                <section className="card">
                  <h2>📜 Analysis History</h2>
                  <div className="history-list">
                    {history.slice(0, 10).map((item) => (
                      <div key={item.id} className="history-item">
                        <div className="history-header">
                          <span className="operation-badge">{item.operation_type.toUpperCase()}</span>
                          <span className="timestamp">{new Date(item.created_at).toLocaleString()}</span>
                        </div>
                        <div className="history-params">
                          <small>{item.parameters}</small>
                        </div>
                        <button onClick={() => restoreFromHistory(item)} className="btn-small">Restore</button>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </>
      )}

      <section className="card status">
        <h3>Status</h3>
        <p className={status.includes("Error") || status.includes("failed") ? "status-error" : "status-ok"}>{status || "Ready"}</p>
      </section>

      {output && (
        <section className="card">
          <h2>📊 Results</h2>
          <div className="output-wrapper">
            <pre>{JSON.stringify(output, null, 2)}</pre>
          </div>
        </section>
      )}
    </main>
  );
}
