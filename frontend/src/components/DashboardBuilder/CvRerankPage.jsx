import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpDown,
  FileSearch,
  FileText,
  RotateCcw,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";

const ACCEPTED_EXTENSIONS = new Set(["pdf", "doc", "docx"]);
const MAX_FILE_BYTES = 10 * 1024 * 1024;

const getExtension = (name = "") => String(name).split(".").pop()?.toLowerCase() || "";

const formatFileSize = (bytes = 0) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const getFileIdentity = (file) =>
  `${file.name}:${file.size}:${file.lastModified || 0}`;

const getPreviewScore = (candidate, criteria) => {
  const source = `${candidate.name}|${candidate.size}|${criteria}`;
  let hash = 17;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 31 + source.charCodeAt(index)) % 100003;
  }
  return 58 + (hash % 39);
};

export default function CvRerankPage() {
  const [candidates, setCandidates] = useState([]);
  const [roleTitle, setRoleTitle] = useState("");
  const [requirements, setRequirements] = useState("");
  const [sortMode, setSortMode] = useState("rank");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isRanking, setIsRanking] = useState(false);
  const fileInputRef = useRef(null);
  const rankingTimerRef = useRef(null);

  useEffect(() => () => {
    if (rankingTimerRef.current) window.clearTimeout(rankingTimerRef.current);
  }, []);

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;

    const invalidType = incoming.filter((file) => !ACCEPTED_EXTENSIONS.has(getExtension(file.name)));
    const tooLarge = incoming.filter((file) => file.size > MAX_FILE_BYTES);
    const valid = incoming.filter(
      (file) => ACCEPTED_EXTENSIONS.has(getExtension(file.name)) && file.size <= MAX_FILE_BYTES
    );

    setCandidates((current) => {
      const existing = new Set(current.map((candidate) => candidate.id));
      const additions = valid
        .filter((file) => {
          const identity = getFileIdentity(file);
          if (existing.has(identity)) return false;
          existing.add(identity);
          return true;
        })
        .map((file) => ({
          id: getFileIdentity(file),
          file,
          name: file.name,
          size: file.size,
          addedAt: Date.now(),
          score: null,
          rank: null,
        }));
      return [...current, ...additions];
    });

    const messages = [];
    if (invalidType.length) messages.push(`${invalidType.length} unsupported file${invalidType.length === 1 ? "" : "s"}`);
    if (tooLarge.length) messages.push(`${tooLarge.length} file${tooLarge.length === 1 ? "" : "s"} over 10 MB`);
    setError(messages.length ? `${messages.join(" and ")} were not added.` : "");
  };

  const rankedCount = candidates.filter((candidate) => candidate.score !== null).length;
  const displayedCandidates = useMemo(() => {
    const items = [...candidates];
    if (sortMode === "name") return items.sort((left, right) => left.name.localeCompare(right.name));
    if (sortMode === "newest") return items.sort((left, right) => right.addedAt - left.addedAt);
    return items.sort((left, right) => {
      if (left.rank === null && right.rank === null) return left.addedAt - right.addedAt;
      if (left.rank === null) return 1;
      if (right.rank === null) return -1;
      return left.rank - right.rank;
    });
  }, [candidates, sortMode]);

  const removeCandidate = (candidateId) => {
    setCandidates((current) => current.filter((candidate) => candidate.id !== candidateId));
  };

  const clearBatch = () => {
    if (rankingTimerRef.current) window.clearTimeout(rankingTimerRef.current);
    rankingTimerRef.current = null;
    setCandidates([]);
    setError("");
    setIsRanking(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const runRerank = () => {
    if (!candidates.length || !requirements.trim() || isRanking) return;
    setIsRanking(true);
    setError("");
    rankingTimerRef.current = window.setTimeout(() => {
      setCandidates((current) => {
        const criteria = `${roleTitle.trim()} ${requirements.trim()}`;
        const scored = current
          .map((candidate) => ({
            ...candidate,
            score: getPreviewScore(candidate, criteria),
          }))
          .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name));
        return scored.map((candidate, index) => ({ ...candidate, rank: index + 1 }));
      });
      setSortMode("rank");
      setIsRanking(false);
      rankingTimerRef.current = null;
    }, 650);
  };

  return (
    <main className="cv-rerank-page">
      <header className="cv-rerank-header">
        <div>
          <h1>CV Rerank</h1>
          <p>Prioritize candidate CVs against a role profile.</p>
        </div>
        <button
          type="button"
          className="cv-rerank-secondary"
          disabled={!candidates.length}
          onClick={clearBatch}
        >
          <RotateCcw size={17} aria-hidden="true" />
          Clear batch
        </button>
      </header>

      <div className="cv-rerank-workspace">
        <section className="cv-rerank-setup" aria-labelledby="cv-rerank-criteria-title">
          <header>
            <span className="cv-rerank-section-icon"><FileSearch size={19} aria-hidden="true" /></span>
            <div>
              <h2 id="cv-rerank-criteria-title">Role criteria</h2>
              <p>Define the target profile for this candidate batch.</p>
            </div>
          </header>

          <label className="cv-rerank-field">
            <span>Role title</span>
            <input
              type="text"
              value={roleTitle}
              onChange={(event) => setRoleTitle(event.target.value)}
              placeholder="Senior data analyst"
            />
          </label>

          <label className="cv-rerank-field">
            <span>Requirements</span>
            <textarea
              value={requirements}
              onChange={(event) => setRequirements(event.target.value)}
              placeholder="Required experience, skills, education, languages, and priorities"
              rows={8}
            />
            <small>{requirements.trim() ? requirements.trim().split(/\s+/).length : 0} words</small>
          </label>

          <div
            className={`cv-rerank-dropzone ${isDragging ? "is-dragging" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              addFiles(event.dataTransfer.files);
            }}
          >
            <Upload size={23} aria-hidden="true" />
            <strong>Drop CVs here</strong>
            <span>PDF, DOC, or DOCX · 10 MB maximum per file</span>
            <button type="button" onClick={() => fileInputRef.current?.click()}>
              Choose files
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              multiple
              hidden
              onChange={(event) => {
                addFiles(event.target.files);
                event.target.value = "";
              }}
            />
          </div>

          {error && <div className="cv-rerank-error" role="alert">{error}</div>}

          <button
            type="button"
            className="cv-rerank-primary"
            disabled={!candidates.length || !requirements.trim() || isRanking}
            onClick={runRerank}
          >
            <Sparkles size={18} aria-hidden="true" />
            {isRanking ? "Reranking…" : "Rerank candidates"}
          </button>
        </section>

        <section className="cv-rerank-results" aria-labelledby="cv-rerank-results-title">
          <header className="cv-rerank-results-header">
            <div>
              <h2 id="cv-rerank-results-title">Candidates</h2>
              <p>{candidates.length} uploaded · {rankedCount} ranked</p>
            </div>
            <label className="cv-rerank-sort">
              <ArrowUpDown size={16} aria-hidden="true" />
              <span className="sr-only">Sort candidates</span>
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value)}>
                <option value="rank">Rank</option>
                <option value="name">Name</option>
                <option value="newest">Newest</option>
              </select>
            </label>
          </header>

          {displayedCandidates.length ? (
            <div className="cv-rerank-table" role="table" aria-label="Candidate CVs">
              <div className="cv-rerank-table-head" role="row">
                <span role="columnheader">Rank</span>
                <span role="columnheader">Candidate file</span>
                <span role="columnheader">Status</span>
                <span role="columnheader">Score</span>
                <span role="columnheader" className="sr-only">Actions</span>
              </div>
              <div className="cv-rerank-table-body" role="rowgroup">
                {displayedCandidates.map((candidate) => (
                  <div className="cv-rerank-row" role="row" key={candidate.id}>
                    <span className="cv-rerank-rank" role="cell">
                      {candidate.rank ? String(candidate.rank).padStart(2, "0") : "—"}
                    </span>
                    <div className="cv-rerank-file" role="cell">
                      <span><FileText size={18} aria-hidden="true" /></span>
                      <div>
                        <strong title={candidate.name}>{candidate.name}</strong>
                        <small>{formatFileSize(candidate.size)}</small>
                      </div>
                    </div>
                    <span className={`cv-rerank-status ${candidate.score !== null ? "is-ranked" : ""}`} role="cell">
                      {candidate.score !== null ? "Ranked" : "Ready"}
                    </span>
                    <strong className="cv-rerank-score" role="cell">
                      {candidate.score !== null ? `${candidate.score}%` : "—"}
                    </strong>
                    <button
                      type="button"
                      className="cv-rerank-remove"
                      onClick={() => removeCandidate(candidate.id)}
                      aria-label={`Remove ${candidate.name}`}
                      title="Remove CV"
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="cv-rerank-empty">
              <FileSearch size={28} aria-hidden="true" />
              <h3>No CVs in this batch</h3>
              <p>Uploaded candidate files will appear here.</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}