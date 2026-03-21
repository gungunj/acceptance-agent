"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type FileRole = "unassigned" | "template" | "asset";
type ParsedTemplate = Record<string, unknown> | null;

type UploadedFileRecord = {
  file_id: string;
  task_id: string;
  filename: string | null;
  content_type: string | null;
  size: number;
  path: string;
  role: FileRole;
  parsed_template: ParsedTemplate;
};

type Task = {
  id: string;
  title: string;
  description: string | null;
  status: "pending";
  template_confirmed?: boolean;
  template_confirmed_at?: string | null;
  files: UploadedFileRecord[];
};

type ParsedField = {
  field: string;
  source: string;
  header?: string;
  context?: string;
  cell_text?: string;
};

type TemplateNodeType = "section" | "field" | "note";
type ContentMode = "generate" | "fill" | "mixed";
type NodeFieldType = "text" | "image" | "table" | "list" | "unknown";
type NodeStatus = "draft" | "confirmed";

type TemplateNode = {
  node_id: string;
  task_id: string;
  node_type: TemplateNodeType;
  title: string;
  level: number;
  parent_id: string | null;
  content_mode: ContentMode;
  field_type: NodeFieldType;
  required: boolean;
  requires_screenshot: boolean;
  enabled: boolean;
  status: NodeStatus;
  normalized_title?: string | null;
  canonical_label?: string | null;
  semantic_tags?: string[];
  normalized_section?: string | null;
  llm_confidence?: number | null;
};

type FillNodeMatchCandidate = {
  unit_id: string;
  file_id: string;
  title: string;
  unit_type: string;
  source_type: string;
  score: number;
  reason: string;
  retrieval_source?: string;
  rerank_score?: number | null;
  rerank_reason?: string | null;
};

type FillNodeMatch = {
  task_id: string;
  node_id: string;
  node_title: string;
  query_text: string;
  expected_unit_types: string[];
  candidates: FillNodeMatchCandidate[];
  selected_unit_id?: string | null;
  evidence_status?: "verified" | "weak" | "missing" | null;
  selection_reason?: string | null;
  retrieval_debug?: Record<string, unknown> | null;
  status: "matched" | "no_candidates" | "skipped";
};

type FillStatus = "ready" | "risky" | "missing";

type FillNodeResult = {
  task_id: string;
  node_id: string;
  node_title: string;
  field_type: NodeFieldType;
  selected_unit_id: string | null;
  evidence_status: "verified" | "weak" | "missing";
  fill_status: FillStatus;
  fill_value: unknown;
  bound_image_unit_id: string | null;
  render_payload: Record<string, unknown> | null;
  generation_confidence?: number | null;
  pending_review?: boolean;
  applied_by_policy?: boolean;
  llm_trace_id?: string | null;
  evidence_unit_ids?: string[];
  risk_note: string | null;
  manual_action: string | null;
};

type GapSeverity = "low" | "medium" | "high";

type GapItem = {
  task_id: string;
  node_id: string;
  node_title: string;
  severity: GapSeverity;
  gap_type: string;
  description: string;
  manual_action: string | null;
};

type SectionDraftStatus = "ready" | "risky" | "missing";

type SectionDraftResult = {
  task_id: string;
  node_id: string;
  node_title: string;
  selected_unit_ids: string[];
  query_text: string;
  draft_text: string;
  evidence_unit_ids?: string[];
  generation_confidence?: number | null;
  llm_trace_id?: string | null;
  inline_assets: Array<{
    type: "image";
    unit_id: string;
    path: string | null;
    caption: string | null;
    position: "after_text" | "appendix";
  }>;
  draft_status: SectionDraftStatus;
  risk_note: string | null;
  manual_action: string | null;
};

type MaterialUnit = {
  id: string;
  task_id: string;
  file_id: string;
  title: string;
  content: string;
  section_index: number;
  source_type?: string;
  unit_type?: string;
  metadata?: Record<string, unknown>;
};

type ResolvedStatus = "ready" | "risky" | "missing" | "skipped";

type ResolvedNode = {
  task_id: string;
  node_id: string;
  node_title: string;
  node_type: TemplateNodeType;
  content_mode: ContentMode;
  level: number;
  parent_id: string | null;
  resolved_status: ResolvedStatus;
  render_payload: Record<string, unknown>;
  source_result_type: string | null;
  source_result_id: string | null;
  gap_count: number;
};

type ResolvedTemplate = {
  ok: boolean;
  task_id: string;
  built_at: string;
  summary?: {
    total_nodes: number;
    ready_nodes: number;
    risky_nodes: number;
    missing_nodes: number;
    export_readiness: "ready" | "risky" | "blocked";
  };
  node_count: number;
  ready_count: number;
  risky_count: number;
  missing_count: number;
  nodes: ResolvedNode[];
  gaps?: GapItem[];
};

type ExportDocument = {
  ok: boolean;
  task_id: string;
  format: "markdown" | "html" | "word";
  generated_at: string;
  file_path: string;
  filename: string;
  content: string | null;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function roleBadgeClass(role: FileRole) {
  if (role === "template") {
    return "border-emerald-300/30 bg-emerald-400/15 text-emerald-100";
  }
  if (role === "asset") {
    return "border-amber-300/30 bg-amber-400/15 text-amber-100";
  }
  return "border-white/10 bg-white/5 text-stone-300";
}

function sectionTitle(role: FileRole) {
  if (role === "template") {
    return "模板文件";
  }
  if (role === "asset") {
    return "素材文件";
  }
  return "未分配文件";
}

function parsedTypeLabel(parsedTemplate: ParsedTemplate): string {
  if (!parsedTemplate) {
    return "unparsed";
  }
  const templateType = parsedTemplate.type;
  return typeof templateType === "string" ? templateType : "parsed";
}

function renderTemplateSummary(parsedTemplate: ParsedTemplate) {
  if (!parsedTemplate) {
    return (
      <div className="mt-5 rounded-2xl border border-dashed border-cyan-300/20 bg-slate-950/40 p-4 text-xs text-stone-400">
        该模板尚未解析，点击“解析模板”后会展示结构摘要。
      </div>
    );
  }

  const summaryEntries = Object.entries(parsedTemplate).filter(
    ([key]) => key !== "preview_paragraphs" && key !== "headings",
  );
  const headings =
    Array.isArray(parsedTemplate.headings) && parsedTemplate.headings.length
      ? parsedTemplate.headings.slice(0, 4)
      : [];
  const previews =
    Array.isArray(parsedTemplate.preview_paragraphs) &&
    parsedTemplate.preview_paragraphs.length
      ? parsedTemplate.preview_paragraphs.slice(0, 3)
      : [];

  return (
    <div className="mt-5 rounded-2xl border border-cyan-300/25 bg-slate-950/60 p-4">
      <p className="text-xs uppercase tracking-[0.25em] text-cyan-300">Template Summary</p>

      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {summaryEntries.map(([key, value]) => (
          <div
            key={key}
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs"
          >
            <dt className="text-stone-400">{key}</dt>
            <dd className="mt-1 break-all text-stone-100">
              {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </dd>
          </div>
        ))}
      </dl>

      {headings.length ? (
        <div className="mt-4">
          <p className="text-xs text-stone-400">Headings</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {headings.map((item) => (
              <span
                key={item}
                className="rounded-full border border-emerald-300/30 bg-emerald-400/15 px-3 py-1 text-xs text-emerald-100"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {previews.length ? (
        <div className="mt-4">
          <p className="text-xs text-stone-400">Preview</p>
          <ul className="mt-2 space-y-2">
            {previews.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-stone-200"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams<{ taskId: string }>();
  const taskId = params.taskId;
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingFileId, setPendingFileId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [templateNodes, setTemplateNodes] = useState<TemplateNode[]>([]);
  const [loadingNodes, setLoadingNodes] = useState(false);
  const [savingNodeId, setSavingNodeId] = useState<string | null>(null);
  const [fillNodeMatches, setFillNodeMatches] = useState<FillNodeMatch[]>([]);
  const [matchingFillNodes, setMatchingFillNodes] = useState(false);
  const [fillNodeResults, setFillNodeResults] = useState<FillNodeResult[]>([]);
  const [loadingFillResults, setLoadingFillResults] = useState(false);
  const [resolvingFillNodes, setResolvingFillNodes] = useState(false);
  const [gapItems, setGapItems] = useState<GapItem[]>([]);
  const [loadingGapItems, setLoadingGapItems] = useState(false);
  const [generatingGaps, setGeneratingGaps] = useState(false);
  const [sectionDrafts, setSectionDrafts] = useState<SectionDraftResult[]>([]);
  const [loadingSectionDrafts, setLoadingSectionDrafts] = useState(false);
  const [generatingSectionDrafts, setGeneratingSectionDrafts] = useState(false);
  const [resolvedTemplate, setResolvedTemplate] = useState<ResolvedTemplate | null>(null);
  const [loadingResolvedTemplate, setLoadingResolvedTemplate] = useState(false);
  const [buildingResolvedTemplate, setBuildingResolvedTemplate] = useState(false);
  const [markdownExport, setMarkdownExport] = useState<ExportDocument | null>(null);
  const [htmlExport, setHtmlExport] = useState<ExportDocument | null>(null);
  const [wordExport, setWordExport] = useState<ExportDocument | null>(null);
  const [exportingMarkdown, setExportingMarkdown] = useState(false);
  const [loadingMarkdownExport, setLoadingMarkdownExport] = useState(false);
  const [exportingHtml, setExportingHtml] = useState(false);
  const [exportingWord, setExportingWord] = useState(false);
  const [materialUnits, setMaterialUnits] = useState<MaterialUnit[]>([]);
  const [parsingMaterials, setParsingMaterials] = useState(false);
  const [normalizingSemantics, setNormalizingSemantics] = useState(false);
  const [buildingEmbeddings, setBuildingEmbeddings] = useState(false);
  const [useHybridLlm, setUseHybridLlm] = useState(true);
  const [compactView, setCompactView] = useState(true);
  const [showTemplateTree, setShowTemplateTree] = useState(false);
  const [showTaskJson, setShowTaskJson] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTaskAndList() {
      try {
        const [detailResponse, listResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/tasks/${taskId}`, {
            cache: "no-store",
          }),
          fetch(`${apiBaseUrl}/tasks`, {
            cache: "no-store",
          }),
        ]);

        if (!detailResponse.ok) {
          throw new Error(`Fetch task detail failed with status ${detailResponse.status}`);
        }
        if (!listResponse.ok) {
          throw new Error(`Fetch task list failed with status ${listResponse.status}`);
        }

        const detailData = (await detailResponse.json()) as Task;
        const listData = (await listResponse.json()) as Task[];
        setTask(detailData);
        setTasks(listData);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load task");
      } finally {
        setLoading(false);
      }
    }

    void loadTaskAndList();
  }, [taskId]);

  useEffect(() => {
    async function loadTemplateNodes() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/template-nodes`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch template nodes failed with status ${response.status}`);
        }
        setTemplateNodes((await response.json()) as TemplateNode[]);
      } catch {
        // If nodes don't exist yet (template not parsed), keep empty.
        setTemplateNodes([]);
      }
    }

    void loadTemplateNodes();
  }, [taskId]);

  useEffect(() => {
    async function loadFillNodeMatches() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/fill-node-matches`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch fill node matches failed with status ${response.status}`);
        }
        setFillNodeMatches((await response.json()) as FillNodeMatch[]);
      } catch {
        setFillNodeMatches([]);
      }
    }

    void loadFillNodeMatches();
  }, [taskId]);

  useEffect(() => {
    async function loadMaterialUnits() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/material-units`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch material units failed with status ${response.status}`);
        }
        setMaterialUnits((await response.json()) as MaterialUnit[]);
      } catch {
        setMaterialUnits([]);
      }
    }

    void loadMaterialUnits();
  }, [taskId]);

  useEffect(() => {
    async function loadFillNodeResults() {
      setLoadingFillResults(true);
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/fill-node-results`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch fill node results failed with status ${response.status}`);
        }
        setFillNodeResults((await response.json()) as FillNodeResult[]);
      } catch {
        setFillNodeResults([]);
      } finally {
        setLoadingFillResults(false);
      }
    }

    void loadFillNodeResults();
  }, [taskId]);

  useEffect(() => {
    async function loadGapItems() {
      setLoadingGapItems(true);
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/gap-items`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch gap items failed with status ${response.status}`);
        }
        setGapItems((await response.json()) as GapItem[]);
      } catch {
        setGapItems([]);
      } finally {
        setLoadingGapItems(false);
      }
    }

    void loadGapItems();
  }, [taskId]);

  useEffect(() => {
    async function loadSectionDrafts() {
      setLoadingSectionDrafts(true);
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/section-drafts`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch section drafts failed with status ${response.status}`);
        }
        setSectionDrafts((await response.json()) as SectionDraftResult[]);
      } catch {
        setSectionDrafts([]);
      } finally {
        setLoadingSectionDrafts(false);
      }
    }

    void loadSectionDrafts();
  }, [taskId]);

  useEffect(() => {
    async function loadResolvedTemplate() {
      setLoadingResolvedTemplate(true);
      try {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/resolved-template`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Fetch resolved template failed with status ${response.status}`);
        }
        setResolvedTemplate((await response.json()) as ResolvedTemplate);
      } catch {
        setResolvedTemplate(null);
      } finally {
        setLoadingResolvedTemplate(false);
      }
    }

    void loadResolvedTemplate();
  }, [taskId]);

  async function updateTemplateNode(nodeId: string, patch: Partial<TemplateNode>) {
    setSavingNodeId(nodeId);
    setError(null);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/tasks/${taskId}/template-nodes/${nodeId}`,
        {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: patch.title,
          node_type: patch.node_type,
          content_mode: patch.content_mode,
          field_type: patch.field_type,
          required: patch.required,
          requires_screenshot: patch.requires_screenshot,
          enabled: patch.enabled,
        }),
      });
      if (!response.ok) {
        throw new Error(`Update template node failed with status ${response.status}`);
      }
      const updated = (await response.json()) as TemplateNode;
      setTemplateNodes((prev) =>
        prev.map((item) => (item.node_id === updated.node_id ? updated : item)),
      );
    } catch (updateError) {
      setError(
        updateError instanceof Error ? updateError.message : "Failed to update template node",
      );
    } finally {
      setSavingNodeId(null);
    }
  }

  async function refreshTaskDetail() {
    const detailResponse = await fetch(`${apiBaseUrl}/tasks/${taskId}`, {
      cache: "no-store",
    });
    if (!detailResponse.ok) {
      throw new Error(`Refresh task detail failed with status ${detailResponse.status}`);
    }
    const updatedTask = (await detailResponse.json()) as Task;
    setTask(updatedTask);
  }

  async function refreshTemplateNodes() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/template-nodes`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setTemplateNodes([]);
        return;
      }
      setTemplateNodes((await response.json()) as TemplateNode[]);
    } catch {
      setTemplateNodes([]);
    }
  }

  async function refreshFillNodeMatches() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/fill-node-matches`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setFillNodeMatches([]);
        return;
      }
      setFillNodeMatches((await response.json()) as FillNodeMatch[]);
    } catch {
      setFillNodeMatches([]);
    }
  }

  async function refreshFillNodeResults() {
    setLoadingFillResults(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/fill-node-results`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setFillNodeResults([]);
        return;
      }
      setFillNodeResults((await response.json()) as FillNodeResult[]);
    } catch {
      setFillNodeResults([]);
    } finally {
      setLoadingFillResults(false);
    }
  }

  async function refreshGapItems() {
    setLoadingGapItems(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/gap-items`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setGapItems([]);
        return;
      }
      setGapItems((await response.json()) as GapItem[]);
    } catch {
      setGapItems([]);
    } finally {
      setLoadingGapItems(false);
    }
  }

  async function refreshSectionDrafts() {
    setLoadingSectionDrafts(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/section-drafts`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setSectionDrafts([]);
        return;
      }
      setSectionDrafts((await response.json()) as SectionDraftResult[]);
    } catch {
      setSectionDrafts([]);
    } finally {
      setLoadingSectionDrafts(false);
    }
  }

  async function refreshResolvedTemplate() {
    setLoadingResolvedTemplate(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/resolved-template`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setResolvedTemplate(null);
        return;
      }
      setResolvedTemplate((await response.json()) as ResolvedTemplate);
    } catch {
      setResolvedTemplate(null);
    } finally {
      setLoadingResolvedTemplate(false);
    }
  }

  async function refreshMarkdownExport() {
    setLoadingMarkdownExport(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-markdown`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setMarkdownExport(null);
        return;
      }
      setMarkdownExport((await response.json()) as ExportDocument);
    } catch {
      setMarkdownExport(null);
    } finally {
      setLoadingMarkdownExport(false);
    }
  }

  async function refreshWordExport() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-word`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setWordExport(null);
        return;
      }
      setWordExport((await response.json()) as ExportDocument);
    } catch {
      setWordExport(null);
    }
  }

  async function refreshMaterialUnits() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/material-units`, {
        cache: "no-store",
      });
      if (!response.ok) {
        setMaterialUnits([]);
        return;
      }
      setMaterialUnits((await response.json()) as MaterialUnit[]);
    } catch {
      setMaterialUnits([]);
    }
  }

  async function refreshTaskList() {
    setLoadingTasks(true);
    try {
      const response = await fetch(`${apiBaseUrl}/tasks`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Fetch task list failed with status ${response.status}`);
      }
      const listData = (await response.json()) as Task[];
      setTasks(listData);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error ? refreshError.message : "Failed to refresh task list",
      );
    } finally {
      setLoadingTasks(false);
    }
  }

  async function updateFileRole(fileId: string, role: "template" | "asset") {
    setPendingFileId(fileId);
    setError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/tasks/${taskId}/files/${fileId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ role }),
      });

      if (!response.ok) {
        throw new Error(`Update file role failed with status ${response.status}`);
      }

      const updatedTask = (await response.json()) as Task;
      setTask(updatedTask);
    } catch (updateError) {
      setError(
        updateError instanceof Error ? updateError.message : "Failed to update file role",
      );
    } finally {
      setPendingFileId(null);
    }
  }

  async function parseTemplate(fileId: string) {
    setPendingFileId(fileId);
    setLoadingNodes(true);
    setError(null);

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/tasks/${taskId}/parse-template?file_id=${encodeURIComponent(fileId)}`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error(`Parse template failed with status ${response.status}`);
      }

      await refreshTaskDetail();
      await refreshTemplateNodes();
    } catch (parseError) {
      setError(
        parseError instanceof Error ? parseError.message : "Failed to parse template",
      );
    } finally {
      setPendingFileId(null);
      setLoadingNodes(false);
    }
  }

  async function confirmTemplate() {
    setLoadingNodes(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/confirm-template`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Confirm template failed with status ${response.status}`);
      }
      const updatedTask = (await response.json()) as Task;
      setTask(updatedTask);
      await refreshTemplateNodes();
    } catch (confirmError) {
      setError(
        confirmError instanceof Error ? confirmError.message : "Failed to confirm template",
      );
    } finally {
      setLoadingNodes(false);
    }
  }

  async function matchFillNodes() {
    setMatchingFillNodes(true);
    setError(null);
    const strategy = useHybridLlm ? "hybrid" : "rule";
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/tasks/${taskId}/match-fill-nodes?top_n=5&strategy=${strategy}`,
        {
          method: "POST",
        },
      );
      if (!response.ok) {
        throw new Error(`Match fill nodes failed with status ${response.status}`);
      }
      await refreshFillNodeMatches();
    } catch (matchError) {
      setError(
        matchError instanceof Error ? matchError.message : "Failed to match fill nodes",
      );
    } finally {
      setMatchingFillNodes(false);
    }
  }

  async function parseMaterials() {
    setParsingMaterials(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/parse-materials`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Parse materials failed with status ${response.status}`);
      }
      await refreshTaskDetail();
      await refreshMaterialUnits();
    } catch (parseError) {
      setError(
        parseError instanceof Error ? parseError.message : "Failed to parse materials",
      );
    } finally {
      setParsingMaterials(false);
    }
  }

  async function resolveFillNodes() {
    setResolvingFillNodes(true);
    setError(null);
    const strategy = useHybridLlm ? "hybrid" : "rule";
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/tasks/${taskId}/resolve-fill-nodes?top_n=5&strategy=${strategy}`,
        {
          method: "POST",
        },
      );
      if (!response.ok) {
        throw new Error(`Resolve fill nodes failed with status ${response.status}`);
      }
      await refreshFillNodeResults();
    } catch (resolveError) {
      setError(
        resolveError instanceof Error ? resolveError.message : "Failed to resolve fill nodes",
      );
    } finally {
      setResolvingFillNodes(false);
    }
  }

  async function generateGaps() {
    setGeneratingGaps(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/generate-gaps`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Generate gaps failed with status ${response.status}`);
      }
      await refreshGapItems();
    } catch (gapError) {
      setError(gapError instanceof Error ? gapError.message : "Failed to generate gaps");
    } finally {
      setGeneratingGaps(false);
    }
  }

  async function generateSectionDrafts() {
    setGeneratingSectionDrafts(true);
    setError(null);
    const strategy = useHybridLlm ? "hybrid" : "rule";
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/tasks/${taskId}/generate-section-drafts?top_n=3&strategy=${strategy}`,
        {
          method: "POST",
        },
      );
      if (!response.ok) {
        throw new Error(`Generate section drafts failed with status ${response.status}`);
      }
      await refreshSectionDrafts();
    } catch (draftError) {
      setError(
        draftError instanceof Error ? draftError.message : "Failed to generate section drafts",
      );
    } finally {
      setGeneratingSectionDrafts(false);
    }
  }

  async function normalizeTemplateSemantics() {
    setNormalizingSemantics(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/normalize-template-semantics`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Normalize template semantics failed with status ${response.status}`);
      }
      await refreshTemplateNodes();
    } catch (normalizeError) {
      setError(
        normalizeError instanceof Error
          ? normalizeError.message
          : "Failed to normalize template semantics",
      );
    } finally {
      setNormalizingSemantics(false);
    }
  }

  async function buildMaterialEmbeddings() {
    setBuildingEmbeddings(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/build-material-embeddings`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Build material embeddings failed with status ${response.status}`);
      }
    } catch (embeddingError) {
      setError(
        embeddingError instanceof Error ? embeddingError.message : "Failed to build material embeddings",
      );
    } finally {
      setBuildingEmbeddings(false);
    }
  }

  async function buildResolvedTemplate() {
    setBuildingResolvedTemplate(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/build-resolved-template`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Build resolved template failed with status ${response.status}`);
      }
      await refreshResolvedTemplate();
    } catch (buildError) {
      setError(
        buildError instanceof Error ? buildError.message : "Failed to build resolved template",
      );
    } finally {
      setBuildingResolvedTemplate(false);
    }
  }

  async function exportMarkdown() {
    setExportingMarkdown(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-markdown`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Export markdown failed with status ${response.status}`);
      }
      setMarkdownExport((await response.json()) as ExportDocument);
      await refreshResolvedTemplate();
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Failed to export markdown");
    } finally {
      setExportingMarkdown(false);
    }
  }

  async function exportHtml() {
    setExportingHtml(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-html`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Export html failed with status ${response.status}`);
      }
      setHtmlExport((await response.json()) as ExportDocument);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Failed to export html");
    } finally {
      setExportingHtml(false);
    }
  }

  async function exportWord() {
    setExportingWord(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-word`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Export word failed with status ${response.status}`);
      }
      setWordExport((await response.json()) as ExportDocument);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Failed to export word");
    } finally {
      setExportingWord(false);
    }
  }

  function downloadText(filename: string, content: string, mimeType: string) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  async function downloadWord() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/export-word/download`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Download word failed with status ${response.status}`);
      }
      const blob = await response.blob();
      const filename = wordExport?.filename ?? `${taskId}.docx`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Failed to download word");
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFiles.length) {
      setError("请先选择要追加上传的文件。");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("task_id", taskId);
      selectedFiles.forEach((file) => formData.append("files", file));

      const response = await fetch(`${apiBaseUrl}/files/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      const detailResponse = await fetch(`${apiBaseUrl}/tasks/${taskId}`, {
        cache: "no-store",
      });

      if (!detailResponse.ok) {
        throw new Error(`Refresh task detail failed with status ${detailResponse.status}`);
      }

      const updatedTask = (await detailResponse.json()) as Task;
      setTask(updatedTask);
      setSelectedFiles([]);
      await refreshTaskList();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload file");
    } finally {
      setUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFiles(Array.from(event.target.files ?? []));
  }

  const templateFiles = task?.files.filter((file) => file.role === "template") ?? [];
  const assetFiles = task?.files.filter((file) => file.role === "asset") ?? [];
  const unassignedFiles = task?.files.filter((file) => file.role === "unassigned") ?? [];
  const groupedFiles: Array<{ role: FileRole; files: UploadedFileRecord[] }> = [
    { role: "template", files: templateFiles },
    { role: "asset", files: assetFiles },
    { role: "unassigned", files: unassignedFiles },
  ];
  const materialUnitById = new Map(materialUnits.map((unit) => [unit.id, unit] as const));

  const templateConfirmed = Boolean(task?.template_confirmed);
  const childrenByParent = new Map<string, TemplateNode[]>();
  templateNodes.forEach((node) => {
    const key = node.parent_id ?? "__root__";
    const list = childrenByParent.get(key) ?? [];
    list.push(node);
    childrenByParent.set(key, list);
  });
  const indexById = new Map(templateNodes.map((node, index) => [node.node_id, index] as const));
  childrenByParent.forEach((list) => {
    list.sort((a, b) => (indexById.get(a.node_id) ?? 0) - (indexById.get(b.node_id) ?? 0));
  });

  function renderNodeRow(node: TemplateNode) {
    const indent = Math.max(0, (node.level ?? 1) - 1) * 12;
    const isField = node.node_type === "field";
    return (
      <div
        key={node.node_id}
        className="flex flex-col gap-2 rounded-2xl border border-white/10 bg-white/5 p-4"
        style={{ marginLeft: indent }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200">
              L{node.level}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
              {node.node_type}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
              {node.status}
            </span>
          </div>
          {savingNodeId === node.node_id ? (
            <span className="text-xs text-cyan-200">保存中...</span>
          ) : null}
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-xs text-stone-400">title</span>
            <input
              className="w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-stone-100 outline-none focus:border-cyan-300/40"
              value={node.title}
              onChange={(event) => {
                const value = event.target.value;
                setTemplateNodes((prev) =>
                  prev.map((item) =>
                    item.node_id === node.node_id ? { ...item, title: value } : item,
                  ),
                );
              }}
              onBlur={() => void updateTemplateNode(node.node_id, { title: node.title })}
            />
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1">
              <span className="text-xs text-stone-400">node_type</span>
              <select
                className="w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-stone-100 outline-none focus:border-cyan-300/40"
                value={node.node_type}
                onChange={(event) => {
                  const value = event.target.value as TemplateNodeType;
                  setTemplateNodes((prev) =>
                    prev.map((item) =>
                      item.node_id === node.node_id ? { ...item, node_type: value } : item,
                    ),
                  );
                  void updateTemplateNode(node.node_id, { node_type: value });
                }}
              >
                <option value="section">section</option>
                <option value="field">field</option>
                <option value="note">note</option>
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-xs text-stone-400">content_mode</span>
              <select
                className="w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-stone-100 outline-none focus:border-cyan-300/40"
                value={node.content_mode}
                onChange={(event) => {
                  const value = event.target.value as ContentMode;
                  setTemplateNodes((prev) =>
                    prev.map((item) =>
                      item.node_id === node.node_id ? { ...item, content_mode: value } : item,
                    ),
                  );
                  void updateTemplateNode(node.node_id, { content_mode: value });
                }}
              >
                <option value="generate">generate</option>
                <option value="fill">fill</option>
                <option value="mixed">mixed</option>
              </select>
            </label>
          </div>

          <label className="space-y-1">
            <span className="text-xs text-stone-400">field_type</span>
            <select
              className="w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-stone-100 outline-none focus:border-cyan-300/40 disabled:cursor-not-allowed disabled:opacity-60"
              value={node.field_type}
              disabled={!isField}
              onChange={(event) => {
                const value = event.target.value as NodeFieldType;
                setTemplateNodes((prev) =>
                  prev.map((item) =>
                    item.node_id === node.node_id ? { ...item, field_type: value } : item,
                  ),
                );
                void updateTemplateNode(node.node_id, { field_type: value });
              }}
            >
              <option value="unknown">unknown</option>
              <option value="text">text</option>
              <option value="image">image</option>
              <option value="table">table</option>
              <option value="list">list</option>
            </select>
          </label>

          <div className="flex flex-wrap items-center gap-4 pt-5 text-sm text-stone-200">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={node.required}
                onChange={(event) => {
                  const value = event.target.checked;
                  setTemplateNodes((prev) =>
                    prev.map((item) =>
                      item.node_id === node.node_id ? { ...item, required: value } : item,
                    ),
                  );
                  void updateTemplateNode(node.node_id, { required: value });
                }}
              />
              required
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={node.requires_screenshot}
                onChange={(event) => {
                  const value = event.target.checked;
                  setTemplateNodes((prev) =>
                    prev.map((item) =>
                      item.node_id === node.node_id
                        ? { ...item, requires_screenshot: value }
                        : item,
                    ),
                  );
                  void updateTemplateNode(node.node_id, { requires_screenshot: value });
                }}
              />
              screenshot
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={node.enabled}
                onChange={(event) => {
                  const value = event.target.checked;
                  setTemplateNodes((prev) =>
                    prev.map((item) =>
                      item.node_id === node.node_id ? { ...item, enabled: value } : item,
                    ),
                  );
                  void updateTemplateNode(node.node_id, { enabled: value });
                }}
              />
              enabled
            </label>
          </div>
        </div>
        <div className="rounded-xl border border-violet-300/20 bg-violet-400/10 px-3 py-2 text-xs text-violet-100">
          <p>canonical_label: {node.canonical_label ?? "n/a"}</p>
          <p>normalized_title: {node.normalized_title ?? "n/a"}</p>
          <p>normalized_section: {node.normalized_section ?? "n/a"}</p>
          <p>semantic_tags: {(node.semantic_tags ?? []).join(", ") || "none"}</p>
          <p>llm_confidence: {node.llm_confidence ?? "n/a"}</p>
        </div>
      </div>
    );
  }

  function renderNodeTree(parentKey: string) {
    const children = childrenByParent.get(parentKey) ?? [];
    if (!children.length) {
      return null;
    }
    return (
      <div className="space-y-3">
        {children.map((node) => (
          <div key={node.node_id} className="space-y-3">
            {renderNodeRow(node)}
            {renderNodeTree(node.node_id)}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full overflow-x-hidden bg-gradient-to-b from-blue-950 via-slate-950 to-black px-6 py-16 text-stone-50">
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.35em] text-cyan-300">Task Detail</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight">
              {task?.title ?? "任务详情"}
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-stone-300">
              {task?.description ?? "该页面会展示任务下的所有上传文件，并允许将文件标记为模板或素材。"}
            </p>
          </div>
          <Link
            className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm text-stone-100 transition hover:bg-white/10"
            href="/"
          >
            返回创建页
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
              compactView
                ? "border-cyan-300/30 bg-cyan-400/15 text-cyan-100 hover:bg-cyan-400/25"
                : "border-white/10 bg-white/5 text-stone-200 hover:bg-white/10"
            }`}
            type="button"
            onClick={() => setCompactView((prev) => !prev)}
          >
            {compactView ? "紧凑模式（当前）" : "切换紧凑模式"}
          </button>
          <p className="text-xs text-stone-400">
            紧凑模式默认隐藏次要信息，核心流程尽量集中在一屏内。
          </p>
        </div>

        {compactView ? (
          <div className="sticky top-3 z-20 rounded-2xl border border-cyan-300/20 bg-slate-950/85 p-3 backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs uppercase tracking-[0.22em] text-cyan-200">Core Flow</p>
              <div className="flex flex-wrap gap-2 text-[11px] text-stone-300">
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                  nodes {templateNodes.length}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                  units {materialUnits.length}
                </span>
                <span className="rounded-full border border-violet-300/20 bg-violet-400/10 px-2 py-1 text-violet-100">
                  pending {fillNodeResults.filter((item) => item.pending_review).length}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                  gaps {gapItems.length}
                </span>
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-4 lg:grid-cols-8">
              <button
                className="rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100 disabled:opacity-50"
                type="button"
                disabled={loadingNodes || !templateFiles.length}
                onClick={() => void parseTemplate(templateFiles[0].file_id)}
              >
                解析模板
              </button>
              <button
                className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-100 disabled:opacity-50"
                type="button"
                disabled={parsingMaterials || !assetFiles.length}
                onClick={() => void parseMaterials()}
              >
                解析素材
              </button>
              <button
                className="rounded-lg border border-indigo-300/30 bg-indigo-400/10 px-3 py-2 text-xs text-indigo-100 disabled:opacity-50"
                type="button"
                disabled={buildingEmbeddings || !materialUnits.length}
                onClick={() => void buildMaterialEmbeddings()}
              >
                构建向量
              </button>
              <button
                className="rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100 disabled:opacity-50"
                type="button"
                disabled={matchingFillNodes || !templateNodes.length || !materialUnits.length}
                onClick={() => void matchFillNodes()}
              >
                匹配 fill
              </button>
              <button
                className="rounded-lg border border-emerald-300/30 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100 disabled:opacity-50"
                type="button"
                disabled={resolvingFillNodes || !fillNodeMatches.length}
                onClick={() => void resolveFillNodes()}
              >
                解析 fill
              </button>
              <button
                className="rounded-lg border border-violet-300/30 bg-violet-400/10 px-3 py-2 text-xs text-violet-100 disabled:opacity-50"
                type="button"
                disabled={generatingSectionDrafts || !materialUnits.length || !templateNodes.length}
                onClick={() => void generateSectionDrafts()}
              >
                章节草稿
              </button>
              <button
                className="rounded-lg border border-fuchsia-300/30 bg-fuchsia-400/10 px-3 py-2 text-xs text-fuchsia-100 disabled:opacity-50"
                type="button"
                disabled={buildingResolvedTemplate || !templateNodes.length}
                onClick={() => void buildResolvedTemplate()}
              >
                构建结果
              </button>
              <button
                className="rounded-lg border border-emerald-300/30 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100 disabled:opacity-50"
                type="button"
                disabled={exportingWord || !templateNodes.length}
                onClick={() => void exportWord()}
              >
                导出 Word
              </button>
            </div>
          </div>
        ) : null}

        <section className="grid gap-8 lg:grid-cols-5">
          <div className="rounded-[2rem] border border-white/10 bg-black/30 p-6 shadow-2xl backdrop-blur lg:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-stone-300">任务元信息</p>
              <button
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200 transition hover:bg-white/10"
                type="button"
                onClick={() => setShowTaskJson((prev) => !prev)}
              >
                {showTaskJson ? "收起 JSON" : "展开 JSON"}
              </button>
            </div>
            {showTaskJson ? (
              <pre className="mt-4 max-h-64 overflow-auto rounded-2xl bg-slate-950/70 p-4 text-sm leading-6 text-stone-100">
                {JSON.stringify(
                  loading
                    ? { loading: true }
                    : task ?? { error: "Task not found" },
                  null,
                  2,
                )}
              </pre>
            ) : (
              <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-stone-300">
                默认收起，避免长 JSON 影响操作。可点击“展开 JSON”查看完整数据。
              </div>
            )}

            <form className="mt-6 space-y-4" onSubmit={handleUpload}>
              <div>
                <p className="text-sm text-stone-300">继续上传更多文件</p>
                <p className="mt-2 text-sm text-stone-400">
                  追加上传的文件会自动挂到当前任务下，并出现在右侧文件列表中。
                </p>
              </div>

              <input
                className="block w-full rounded-2xl border border-dashed border-white/15 bg-white/5 px-4 py-3 text-sm text-stone-300 file:mr-4 file:rounded-full file:border-0 file:bg-cyan-300 file:px-4 file:py-2 file:text-sm file:font-medium file:text-slate-950"
                type="file"
                multiple
                onChange={handleFileChange}
              />
              {selectedFiles.length ? (
                <p className="text-xs text-stone-400">
                  已选择 {selectedFiles.length} 个文件：
                  {" "}
                  {selectedFiles.map((file) => file.name).join(" / ")}
                </p>
              ) : null}

              <button
                className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-cyan-300/50"
                type="submit"
                disabled={uploading}
              >
                {uploading ? "上传中..." : "上传选中文件"}
              </button>
            </form>

            {!compactView ? (
              <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">任务列表</p>
                <button
                  className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={loadingTasks}
                  onClick={() => void refreshTaskList()}
                >
                  {loadingTasks ? "刷新中..." : "刷新任务列表"}
                </button>
              </div>
              <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
                {tasks.length ? (
                  tasks.map((item) => (
                    <Link
                      key={item.id}
                      className={`block rounded-xl border px-3 py-2 text-sm transition ${
                        item.id === taskId
                          ? "border-cyan-300/30 bg-cyan-400/10 text-cyan-100"
                          : "border-white/10 bg-white/5 text-stone-200 hover:border-cyan-300/20"
                      }`}
                      href={`/tasks/${item.id}`}
                    >
                      <p className="font-medium">{item.title}</p>
                      <p className="mt-1 font-mono text-xs text-stone-400">{item.id}</p>
                    </Link>
                  ))
                ) : (
                  <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-2 text-sm text-stone-400">
                    暂无任务。
                  </p>
                )}
              </div>
              </div>
            ) : null}

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">模板结构</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {templateNodes.length} nodes
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                    useHybridLlm
                      ? "border-violet-300/30 bg-violet-400/15 text-violet-100 hover:bg-violet-400/25"
                      : "border-white/10 bg-white/5 text-stone-200 hover:bg-white/10"
                  }`}
                  type="button"
                  onClick={() => setUseHybridLlm((prev) => !prev)}
                >
                  LLM处理：{useHybridLlm ? "开启(hybrid)" : "关闭(rule)"}
                </button>
                <button
                  className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={loadingNodes || !templateFiles.length}
                  onClick={() => void parseTemplate(templateFiles[0].file_id)}
                >
                  {loadingNodes ? "解析中..." : "解析模板(生成节点)"}
                </button>
                <button
                  className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={loadingNodes || !templateNodes.length || templateConfirmed}
                  onClick={() => void confirmTemplate()}
                >
                  {templateConfirmed ? "已确认" : "确认模板"}
                </button>
                <button
                  className="rounded-full border border-violet-300/30 bg-violet-400/10 px-4 py-2 text-sm font-medium text-violet-100 transition hover:bg-violet-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={normalizingSemantics || !templateNodes.length}
                  onClick={() => void normalizeTemplateSemantics()}
                >
                  {normalizingSemantics ? "标准化中..." : "语义标准化"}
                </button>
                <button
                  className="rounded-full border border-indigo-300/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={buildingEmbeddings || !materialUnits.length}
                  onClick={() => void buildMaterialEmbeddings()}
                >
                  {buildingEmbeddings ? "构建中..." : "构建素材向量"}
                </button>
              </div>

              {templateNodes.length ? (
                compactView && !showTemplateTree ? (
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <p className="text-xs text-stone-300">
                      已解析 {templateNodes.length} 个节点。为保证一屏操作，结构树默认折叠。
                    </p>
                    <button
                      className="mt-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200 transition hover:bg-white/10"
                      type="button"
                      onClick={() => setShowTemplateTree(true)}
                    >
                      展开模板结构树
                    </button>
                  </div>
                ) : (
                  <div className="max-h-[22rem] overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/40 p-3">
                    {renderNodeTree("__root__")}
                    {compactView ? (
                      <button
                        className="mt-3 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-200 transition hover:bg-white/10"
                        type="button"
                        onClick={() => setShowTemplateTree(false)}
                      >
                        收起模板结构树
                      </button>
                    ) : null}
                  </div>
                )
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  还没有模板节点。先把某个文件设为模板并点击“解析模板(生成节点)”。
                </p>
              )}
            </div>

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">Fill 节点候选匹配</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {fillNodeMatches.length} nodes
                </span>
              </div>

              <button
                className="rounded-full border border-amber-300/30 bg-amber-400/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                type="button"
                disabled={matchingFillNodes || !templateNodes.length}
                onClick={() => void matchFillNodes()}
              >
                {matchingFillNodes ? "匹配中..." : "开始匹配 fill 节点"}
              </button>

              {fillNodeMatches.length ? (
                <details
                  className="rounded-2xl border border-white/10 bg-slate-950/40 p-3"
                  open={!compactView}
                >
                  <summary className="cursor-pointer text-sm text-stone-200">
                    查看匹配详情（{fillNodeMatches.length}）
                  </summary>
                  <div className="mt-3 max-h-[24rem] space-y-3 overflow-y-auto">
                    {fillNodeMatches.map((match) => (
                      <div key={match.node_id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-stone-100">{match.node_title}</p>
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-stone-300">
                            {match.status}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-stone-400">query: {match.query_text}</p>
                        <p className="mt-1 text-xs text-stone-500">
                          expected: {match.expected_unit_types.join(", ") || "none"}
                        </p>
                        <p className="mt-1 text-xs text-stone-500">
                          selected_unit_id: {match.selected_unit_id ?? "none"} · evidence_status:{" "}
                          {match.evidence_status ?? "n/a"}
                        </p>
                        {match.selection_reason ? (
                          <p className="mt-1 text-xs text-stone-500">selection_reason: {match.selection_reason}</p>
                        ) : null}
                        <div className="mt-3 space-y-2">
                          {match.candidates.length ? (
                            match.candidates.map((candidate) => (
                              <div
                                key={`${match.node_id}-${candidate.unit_id}`}
                                className="rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 text-xs"
                              >
                                <p className="text-stone-100">{candidate.title}</p>
                                <p className="mt-1 text-stone-400">
                                  {candidate.unit_type} · score {candidate.score}
                                </p>
                                <p className="mt-1 text-stone-500">{candidate.reason}</p>
                                <p className="mt-1 text-stone-500">
                                  source: {candidate.retrieval_source ?? "rule"} · rerank:{" "}
                                  {candidate.rerank_score ?? "n/a"}
                                </p>
                                {candidate.rerank_reason ? (
                                  <p className="mt-1 text-stone-500">rerank_reason: {candidate.rerank_reason}</p>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-2 text-xs text-stone-400">
                              暂无候选证据。
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  还没有匹配结果。先确认模板并完成素材解析，然后点击“开始匹配 fill 节点”。
                </p>
              )}
            </div>

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">Fill Node Results</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {fillNodeResults.length} results
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={resolvingFillNodes || !fillNodeMatches.length}
                  onClick={() => void resolveFillNodes()}
                >
                  {resolvingFillNodes ? "解析中..." : "解析 fill 结果"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={loadingFillResults}
                  onClick={() => void refreshFillNodeResults()}
                >
                  {loadingFillResults ? "加载中..." : "刷新结果"}
                </button>
              </div>

              {fillNodeResults.length ? (
                <details className="rounded-2xl border border-white/10 bg-slate-950/40 p-3" open={!compactView}>
                  <summary className="cursor-pointer text-sm text-stone-200">
                    查看 fill 结果详情（{fillNodeResults.length}）
                  </summary>
                  <div className="mt-3 max-h-[26rem] space-y-3 overflow-y-auto">
                    <div className="rounded-xl border border-violet-300/20 bg-violet-400/10 px-3 py-2 text-xs text-violet-100">
                      待确认结果：{fillNodeResults.filter((item) => item.pending_review).length}；自动写回：
                      {" "}
                      {fillNodeResults.filter((item) => item.applied_by_policy).length}
                    </div>
                    {fillNodeResults.map((item) => (
                      <div key={item.node_id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-stone-100">{item.node_title}</p>
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-stone-300">
                            {item.evidence_status}
                          </span>
                          <span className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-2 py-1 text-[11px] text-cyan-100">
                            {item.fill_status}
                          </span>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-stone-300">
                        <p>selected_unit_id: {item.selected_unit_id ?? "none"}</p>
                        <p>field_type: {item.field_type}</p>
                        <p>bound_image_unit_id: {item.bound_image_unit_id ?? "none"}</p>
                        <p>pending_review: {String(item.pending_review ?? false)}</p>
                        <p>applied_by_policy: {String(item.applied_by_policy ?? false)}</p>
                        <p>generation_confidence: {item.generation_confidence ?? "n/a"}</p>
                        <p>llm_trace_id: {item.llm_trace_id ?? "n/a"}</p>
                        <p>evidence_unit_ids: {(item.evidence_unit_ids ?? []).join(", ") || "none"}</p>
                      </div>
                      {item.bound_image_unit_id ? (
                        <div className="mt-2 rounded-xl border border-indigo-300/20 bg-indigo-400/10 px-3 py-2 text-xs text-indigo-100">
                          {(() => {
                            const imageUnit = materialUnitById.get(item.bound_image_unit_id ?? "");
                            const path =
                              (imageUnit?.metadata?.path as string | undefined) ??
                              (imageUnit?.metadata?.file_path as string | undefined) ??
                              (imageUnit?.metadata?.asset_path as string | undefined) ??
                              "";
                            const fileLabel = imageUnit?.title || "image";
                            return `已绑定图片：${fileLabel}${path ? ` (${path})` : ""}`;
                          })()}
                        </div>
                      ) : null}
                      {item.risk_note ? (
                        <p className="mt-2 rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
                          风险：{item.risk_note}
                        </p>
                      ) : null}
                      {item.manual_action ? (
                        <p className="mt-2 rounded-xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100">
                          操作建议：{item.manual_action}
                        </p>
                      ) : null}
                      <details className="mt-2 rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2">
                        <summary className="cursor-pointer text-xs text-stone-300">
                          fill_value / render_payload
                        </summary>
                        <pre className="mt-2 max-h-40 overflow-auto text-xs text-stone-200">
                          {JSON.stringify(
                            {
                              fill_value: item.fill_value,
                              render_payload: item.render_payload,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  {loadingFillResults
                    ? "正在加载 fill 结果..."
                    : "暂无 fill 结果。先完成“匹配 fill 节点”，再点击“解析 fill 结果”。"}
                </p>
              )}
            </div>

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">Gap Items</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {gapItems.length} gaps
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-rose-300/30 bg-rose-400/10 px-4 py-2 text-sm font-medium text-rose-100 transition hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={generatingGaps || !fillNodeResults.length}
                  onClick={() => void generateGaps()}
                >
                  {generatingGaps ? "生成中..." : "生成缺口清单"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={loadingGapItems}
                  onClick={() => void refreshGapItems()}
                >
                  {loadingGapItems ? "加载中..." : "刷新缺口"}
                </button>
              </div>

              {gapItems.length ? (
                <details className="rounded-2xl border border-white/10 bg-slate-950/40 p-3" open={!compactView}>
                  <summary className="cursor-pointer text-sm text-stone-200">
                    查看缺口详情（{gapItems.length}）
                  </summary>
                  <div className="mt-3 max-h-[26rem] space-y-3 overflow-y-auto">
                    {gapItems.map((item, idx) => (
                      <div
                        key={`${item.node_id}-${idx}`}
                        className="rounded-2xl border border-white/10 bg-white/5 p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-stone-100">{item.node_title}</p>
                          <span
                            className={`rounded-full border px-2 py-1 text-[11px] ${
                              item.severity === "high"
                                ? "border-rose-300/30 bg-rose-400/15 text-rose-100"
                                : item.severity === "medium"
                                  ? "border-amber-300/30 bg-amber-400/15 text-amber-100"
                                  : "border-cyan-300/30 bg-cyan-400/15 text-cyan-100"
                            }`}
                          >
                            {item.severity}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-stone-400">type: {item.gap_type}</p>
                        <p className="mt-2 text-sm text-stone-200">{item.description}</p>
                        {item.manual_action ? (
                          <p className="mt-2 rounded-xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100">
                            操作建议：{item.manual_action}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  {loadingGapItems
                    ? "正在加载缺口清单..."
                    : "暂无缺口项。点击“生成缺口清单”生成并落盘。"}
                </p>
              )}
            </div>

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">Section Drafts</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {sectionDrafts.length} drafts
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-indigo-300/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={generatingSectionDrafts || !materialUnits.length || !templateNodes.length}
                  onClick={() => void generateSectionDrafts()}
                >
                  {generatingSectionDrafts ? "生成中..." : "生成章节草稿"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={loadingSectionDrafts}
                  onClick={() => void refreshSectionDrafts()}
                >
                  {loadingSectionDrafts ? "加载中..." : "刷新草稿"}
                </button>
              </div>

              {sectionDrafts.length ? (
                <details className="rounded-2xl border border-white/10 bg-slate-950/40 p-3" open={!compactView}>
                  <summary className="cursor-pointer text-sm text-stone-200">
                    查看章节草稿详情（{sectionDrafts.length}）
                  </summary>
                  <div className="mt-3 max-h-[26rem] space-y-3 overflow-y-auto">
                    {sectionDrafts.map((item) => (
                      <div key={item.node_id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-stone-100">{item.node_title}</p>
                        <span
                          className={`rounded-full border px-2 py-1 text-[11px] ${
                            item.draft_status === "ready"
                              ? "border-emerald-300/30 bg-emerald-400/15 text-emerald-100"
                              : item.draft_status === "risky"
                                ? "border-amber-300/30 bg-amber-400/15 text-amber-100"
                                : "border-rose-300/30 bg-rose-400/15 text-rose-100"
                          }`}
                        >
                          {item.draft_status}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-stone-400">query: {item.query_text}</p>
                      <p className="mt-1 text-xs text-stone-400">
                        selected units: {item.selected_unit_ids.length}
                      </p>
                      <p className="mt-1 text-xs text-stone-400">
                        confidence: {item.generation_confidence ?? "n/a"} · evidence:
                        {" "}
                        {(item.evidence_unit_ids ?? []).length}
                        {" "}
                        · llm_trace_id: {item.llm_trace_id ?? "n/a"}
                      </p>
                      <p className="mt-1 text-xs text-stone-400">
                        inline assets: {item.inline_assets?.length ?? 0}
                      </p>
                      {item.risk_note ? (
                        <p className="mt-2 rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
                          风险：{item.risk_note}
                        </p>
                      ) : null}
                      {item.manual_action ? (
                        <p className="mt-2 rounded-xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100">
                          操作建议：{item.manual_action}
                        </p>
                      ) : null}
                      <details className="mt-2 rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2">
                        <summary className="cursor-pointer text-xs text-stone-300">draft_text</summary>
                        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-xs text-stone-200">
                          {item.draft_text || "(empty)"}
                        </pre>
                      </details>
                      {item.inline_assets?.length ? (
                        <details className="mt-2 rounded-xl border border-indigo-300/20 bg-indigo-400/10 px-3 py-2">
                          <summary className="cursor-pointer text-xs text-indigo-100">
                            inline image assets
                          </summary>
                          <div className="mt-2 space-y-2">
                            {item.inline_assets.map((asset, index) => {
                              const unit = materialUnitById.get(asset.unit_id);
                              const path = asset.path || ((unit?.metadata?.path as string | undefined) ?? "");
                              return (
                                <div
                                  key={`${item.node_id}-${asset.unit_id}-${index}`}
                                  className="rounded-lg border border-white/10 bg-slate-950/40 p-2 text-xs text-stone-200"
                                >
                                  <p>unit_id: {asset.unit_id}</p>
                                  <p>caption: {asset.caption || unit?.title || "(none)"}</p>
                                  <p>position: {asset.position}</p>
                                  <p>path: {path || "(unknown)"}</p>
                                </div>
                              );
                            })}
                          </div>
                        </details>
                      ) : null}
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  {loadingSectionDrafts
                    ? "正在加载章节草稿..."
                    : "暂无章节草稿。点击“生成章节草稿”后可查看 generate 节点结果。"}
                </p>
              )}
            </div>

            <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">Resolved Template</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  {resolvedTemplate?.node_count ?? 0} nodes
                </span>
              </div>

              {resolvedTemplate?.summary ? (
                <div className="grid gap-2 rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-stone-200 sm:grid-cols-5">
                  <p>total: {resolvedTemplate.summary.total_nodes}</p>
                  <p>ready: {resolvedTemplate.summary.ready_nodes}</p>
                  <p>risky: {resolvedTemplate.summary.risky_nodes}</p>
                  <p>missing: {resolvedTemplate.summary.missing_nodes}</p>
                  <p>readiness: {resolvedTemplate.summary.export_readiness}</p>
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-fuchsia-300/30 bg-fuchsia-400/10 px-4 py-2 text-sm font-medium text-fuchsia-100 transition hover:bg-fuchsia-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={buildingResolvedTemplate || !templateNodes.length}
                  onClick={() => void buildResolvedTemplate()}
                >
                  {buildingResolvedTemplate ? "构建中..." : "构建 Resolved Template"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={loadingResolvedTemplate}
                  onClick={() => void refreshResolvedTemplate()}
                >
                  {loadingResolvedTemplate ? "加载中..." : "刷新预览"}
                </button>
                <button
                  className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={exportingMarkdown || !templateNodes.length}
                  onClick={() => void exportMarkdown()}
                >
                  {exportingMarkdown ? "导出中..." : "导出 Markdown"}
                </button>
                <button
                  className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={exportingHtml || !templateNodes.length}
                  onClick={() => void exportHtml()}
                >
                  {exportingHtml ? "导出中..." : "导出 HTML"}
                </button>
                <button
                  className="rounded-full border border-indigo-300/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={exportingWord || !templateNodes.length}
                  onClick={() => void exportWord()}
                >
                  {exportingWord ? "导出中..." : "导出 Word"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={loadingMarkdownExport}
                  onClick={() => void refreshMarkdownExport()}
                >
                  {loadingMarkdownExport ? "加载中..." : "刷新 Markdown"}
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  onClick={() => void refreshWordExport()}
                >
                  刷新 Word
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={!markdownExport?.content}
                  onClick={() =>
                    markdownExport?.content
                      ? downloadText(markdownExport.filename, markdownExport.content, "text/markdown")
                      : undefined
                  }
                >
                  下载 Markdown
                </button>
                <button
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  disabled={!wordExport}
                  onClick={() => void downloadWord()}
                >
                  下载 Word
                </button>
              </div>

              {resolvedTemplate?.nodes?.length ? (
                <details className="rounded-2xl border border-white/10 bg-slate-950/40 p-3" open={!compactView}>
                  <summary className="cursor-pointer text-sm text-stone-200">
                    查看 resolved 节点详情（{resolvedTemplate.nodes.length}）
                  </summary>
                  <div className="mt-3 max-h-[26rem] space-y-3 overflow-y-auto">
                    {resolvedTemplate.nodes.map((node) => (
                      <div key={node.node_id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-stone-100">{node.node_title}</p>
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-stone-300">
                          {node.resolved_status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-stone-400">
                        {node.node_type} · {node.content_mode}
                      </p>
                      <details className="mt-2 rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2">
                        <summary className="cursor-pointer text-xs text-stone-300">render_payload</summary>
                        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-xs text-stone-200">
                          {JSON.stringify(node.render_payload, null, 2)}
                        </pre>
                      </details>
                      </div>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-3 text-sm text-stone-400">
                  {loadingResolvedTemplate
                    ? "正在加载 resolved template..."
                    : "暂无 resolved template。先完成 fill / section drafts，再点击构建。"}
                </p>
              )}

              {markdownExport?.content ? (
                <details className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-3">
                  <summary className="cursor-pointer text-sm text-emerald-100">
                    Markdown 预览（{markdownExport.filename}）
                  </summary>
                  <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-emerald-50">
                    {markdownExport.content}
                  </pre>
                </details>
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-2 text-xs text-stone-400">
                  尚未生成 Markdown 导出结果。
                </p>
              )}

              {htmlExport?.content ? (
                <details className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-3">
                  <summary className="cursor-pointer text-sm text-cyan-100">
                    HTML 导出（{htmlExport.filename}）
                  </summary>
                  <p className="mt-2 text-xs text-cyan-50">已生成 HTML 文件：{htmlExport.file_path}</p>
                  <button
                    className="mt-2 rounded-full border border-cyan-200/30 bg-cyan-200/10 px-3 py-1 text-xs text-cyan-50"
                    type="button"
                    onClick={() =>
                      downloadText(htmlExport.filename, htmlExport.content, "text/html")
                    }
                  >
                    下载 HTML
                  </button>
                </details>
              ) : null}

              {wordExport ? (
                <details className="rounded-2xl border border-indigo-300/20 bg-indigo-400/10 p-3">
                  <summary className="cursor-pointer text-sm text-indigo-100">
                    Word 导出（{wordExport.filename}）
                  </summary>
                  <p className="mt-2 text-xs text-indigo-50">已生成 Word 文件：{wordExport.file_path}</p>
                  <button
                    className="mt-2 rounded-full border border-indigo-200/30 bg-indigo-200/10 px-3 py-1 text-xs text-indigo-50"
                    type="button"
                    onClick={() => void downloadWord()}
                  >
                    下载 Word
                  </button>
                </details>
              ) : null}
            </div>

            {!compactView ? (
              <div className="mt-8 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-stone-300">下一步操作</p>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  素材单元 {materialUnits.length}
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  className="rounded-xl border border-amber-300/30 bg-amber-400/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={parsingMaterials || !assetFiles.length}
                  onClick={() => void parseMaterials()}
                >
                  {parsingMaterials ? "素材解析中..." : "1) 解析素材"}
                </button>
                <button
                  className="rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={matchingFillNodes || !templateNodes.length || !materialUnits.length}
                  onClick={() => void matchFillNodes()}
                >
                  {matchingFillNodes ? "匹配中..." : "2) 匹配 fill 节点"}
                </button>
                <button
                  className="rounded-xl border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={resolvingFillNodes || !fillNodeMatches.length}
                  onClick={() => void resolveFillNodes()}
                >
                  {resolvingFillNodes ? "解析中..." : "3) 解析 fill 结果"}
                </button>
                <button
                  className="rounded-xl border border-rose-300/30 bg-rose-400/10 px-4 py-2 text-sm font-medium text-rose-100 transition hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={generatingGaps || !fillNodeResults.length}
                  onClick={() => void generateGaps()}
                >
                  {generatingGaps ? "生成中..." : "4) 生成缺口清单"}
                </button>
                <button
                  className="rounded-xl border border-indigo-300/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={generatingSectionDrafts || !materialUnits.length || !templateNodes.length}
                  onClick={() => void generateSectionDrafts()}
                >
                  {generatingSectionDrafts ? "生成中..." : "5) 生成章节草稿"}
                </button>
                <button
                  className="rounded-xl border border-fuchsia-300/30 bg-fuchsia-400/10 px-4 py-2 text-sm font-medium text-fuchsia-100 transition hover:bg-fuchsia-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={buildingResolvedTemplate || !templateNodes.length}
                  onClick={() => void buildResolvedTemplate()}
                >
                  {buildingResolvedTemplate ? "构建中..." : "6) 构建 resolved template"}
                </button>
                <button
                  className="rounded-xl border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={exportingMarkdown || !templateNodes.length}
                  onClick={() => void exportMarkdown()}
                >
                  {exportingMarkdown ? "导出中..." : "7) 导出 Markdown"}
                </button>
                <button
                  className="rounded-xl border border-indigo-300/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-100 transition hover:bg-indigo-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                  type="button"
                  disabled={exportingWord || !templateNodes.length}
                  onClick={() => void exportWord()}
                >
                  {exportingWord ? "导出中..." : "8) 导出 Word"}
                </button>
              </div>

              <p className="rounded-xl border border-dashed border-white/10 bg-white/5 px-3 py-2 text-xs text-stone-400">
                建议顺序：解析模板并确认 → 解析素材 → 匹配/解析 fill → 生成章节草稿 → 构建
                resolved template → 导出 Markdown/Word。
              </p>
              </div>
            ) : null}
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-black/30 p-6 shadow-2xl backdrop-blur lg:col-span-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-stone-300">上传文件</p>
                <p className="mt-2 text-sm text-stone-400">
                  当前任务下的全部文件都会列在这里，可设为模板或素材。
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                {task?.files.length ?? 0} files
              </span>
            </div>

            {error ? (
              <div className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-400/10 p-4 text-sm text-rose-100">
                {error}
              </div>
            ) : null}

            {task?.files.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-emerald-300/30 bg-emerald-400/15 px-3 py-1 text-xs text-emerald-100">
                  模板 {templateFiles.length}
                </span>
                <span className="rounded-full border border-amber-300/30 bg-amber-400/15 px-3 py-1 text-xs text-amber-100">
                  素材 {assetFiles.length}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                  未分配 {unassignedFiles.length}
                </span>
              </div>
            ) : null}

            <div className="mt-6 space-y-6">
              {task?.files.length ? (
                groupedFiles.map((group) => (
                  <section key={group.role} className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold tracking-wide text-stone-200">
                        {sectionTitle(group.role)}
                      </h3>
                      <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                        {group.files.length}
                      </span>
                    </div>

                    {group.files.length ? (
                      group.files.map((file) => (
                        <details
                          key={file.file_id}
                          className="rounded-3xl border border-white/10 bg-white/5 p-5"
                          open={!compactView}
                        >
                          <summary className="cursor-pointer list-none">
                            <div className="flex flex-wrap items-start justify-between gap-4">
                              <div className="space-y-2">
                                <p className="text-base font-medium text-white">
                                  {file.filename ?? "未命名文件"}
                                </p>
                                <p className="font-mono text-xs text-stone-400">{file.path}</p>
                                <div className="flex flex-wrap gap-2 text-xs text-stone-300">
                                  <span>{file.size} bytes</span>
                                  <span>{file.content_type ?? "unknown content-type"}</span>
                                </div>
                              </div>
                              <span
                                className={`rounded-full border px-3 py-1 text-xs ${roleBadgeClass(file.role)}`}
                              >
                                {file.role} · {parsedTypeLabel(file.parsed_template)}
                              </span>
                            </div>
                          </summary>

                          <div className="mt-5 flex flex-wrap gap-3">
                            <button
                              className="rounded-full bg-emerald-300 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-emerald-300/50"
                              type="button"
                              disabled={pendingFileId === file.file_id}
                              onClick={() => updateFileRole(file.file_id, "template")}
                            >
                              设为模板
                            </button>
                            <button
                              className="rounded-full bg-amber-300 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:bg-amber-300/50"
                              type="button"
                              disabled={pendingFileId === file.file_id}
                              onClick={() => updateFileRole(file.file_id, "asset")}
                            >
                              设为素材
                            </button>
                            <button
                              className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-stone-500"
                              type="button"
                              disabled={pendingFileId === file.file_id || file.role !== "template"}
                              onClick={() => parseTemplate(file.file_id)}
                            >
                              解析模板
                            </button>
                          </div>

                          {group.role === "template"
                            ? renderTemplateSummary(file.parsed_template)
                            : null}

                          {group.role === "template" &&
                          file.parsed_template &&
                          Array.isArray(file.parsed_template.field_list) ? (
                            <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-4">
                              <p className="text-xs uppercase tracking-[0.25em] text-emerald-200">
                                字段列表
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                {(file.parsed_template.field_list as ParsedField[]).map(
                                  (field) => (
                                    <span
                                      key={`${field.source}-${field.field}-${field.header ?? ""}`}
                                      className="rounded-full border border-emerald-300/30 bg-emerald-500/15 px-3 py-1 text-xs text-emerald-100"
                                      title={
                                        field.header
                                          ? `${field.field} | ${field.source} | ${field.header}`
                                          : `${field.field} | ${field.source}`
                                      }
                                    >
                                      {field.field}
                                    </span>
                                  ),
                                )}
                              </div>
                            </div>
                          ) : null}
                        </details>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-5 text-sm text-stone-400">
                        当前分组暂无文件。
                      </div>
                    )}
                  </section>
                ))
              ) : (
                <div className="rounded-3xl border border-dashed border-white/10 bg-white/5 p-8 text-sm text-stone-400">
                  这个任务下还没有文件。
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
