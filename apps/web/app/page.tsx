"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type HealthResponse = {
  ok: boolean;
  service: string;
  status: string;
};

type UploadedFileRecord = {
  file_id: string;
  task_id: string;
  filename: string | null;
  content_type: string | null;
  size: number;
  path: string;
};

type Task = {
  id: string;
  title: string;
  description: string | null;
  status: "pending";
  files: UploadedFileRecord[];
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`);
        if (!response.ok) {
          throw new Error(`Health check failed with status ${response.status}`);
        }

        const data = (await response.json()) as HealthResponse;
        if (active) {
          setHealth(data);
        }
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof Error ? loadError.message : "Failed to reach API",
          );
        }
      }
    }

    void loadHealth();

    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setError("请先选择一个模板或素材文件。");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const taskResponse = await fetch(`${apiBaseUrl}/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          description: description || null,
        }),
      });

      if (!taskResponse.ok) {
        throw new Error(`Create task failed with status ${taskResponse.status}`);
      }

      const createdTask = (await taskResponse.json()) as Task;

      const formData = new FormData();
      formData.append("task_id", createdTask.id);
      formData.append("file", selectedFile);

      const uploadResponse = await fetch(`${apiBaseUrl}/files/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        throw new Error(`Upload failed with status ${uploadResponse.status}`);
      }

      const detailResponse = await fetch(`${apiBaseUrl}/tasks/${createdTask.id}`, {
        cache: "no-store",
      });

      if (!detailResponse.ok) {
        throw new Error(`Fetch task detail failed with status ${detailResponse.status}`);
      }

      const detail = (await detailResponse.json()) as Task;
      setTask(detail);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Request failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#1f2937,_#09090b_55%)] px-6 py-16 text-stone-50">
      <main className="mx-auto grid w-full max-w-6xl gap-8 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-[2rem] border border-white/10 bg-black/30 p-8 shadow-2xl backdrop-blur">
          <div className="space-y-4">
            <p className="text-sm uppercase tracking-[0.35em] text-cyan-300">
              Acceptance Agent
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-white">
              创建任务并上传模板 / 素材
            </h1>
            <p className="max-w-2xl text-base leading-7 text-stone-300">
              当前页面会串起整套链路：前端创建任务，上传文件到后端落盘，再根据返回的
              <code className="mx-1 rounded bg-white/10 px-1.5 py-0.5 text-sm">
                task_id
              </code>
              拉取并展示任务详情。
            </p>
          </div>

          <form className="mt-10 space-y-6" onSubmit={handleSubmit}>
            <div className="grid gap-6 md:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm text-stone-300">任务标题</span>
                <input
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300"
                  placeholder="例如：电商主图审核"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  required
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm text-stone-300">模板 / 素材文件</span>
                <input
                  className="block w-full rounded-2xl border border-dashed border-white/15 bg-white/5 px-4 py-3 text-sm text-stone-300 file:mr-4 file:rounded-full file:border-0 file:bg-cyan-300 file:px-4 file:py-2 file:text-sm file:font-medium file:text-slate-950"
                  type="file"
                  onChange={handleFileChange}
                  required
                />
              </label>
            </div>

            <label className="block">
              <span className="mb-2 block text-sm text-stone-300">任务描述</span>
              <textarea
                className="min-h-32 w-full rounded-3xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-cyan-300"
                placeholder="描述这个任务需要处理什么内容"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>

            <div className="flex flex-wrap items-center gap-4">
              <button
                className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-cyan-300/50"
                type="submit"
                disabled={submitting}
              >
                {submitting ? "处理中..." : "创建任务并上传"}
              </button>
              {selectedFile ? (
                <p className="text-sm text-stone-400">
                  已选择文件：{selectedFile.name}
                </p>
              ) : null}
            </div>
          </form>

          {error ? (
            <div className="mt-6 rounded-2xl border border-rose-400/30 bg-rose-400/10 p-4 text-sm text-rose-100">
              {error}
            </div>
          ) : null}
        </section>

        <section className="space-y-6">
          <div className="rounded-[2rem] border border-cyan-300/20 bg-cyan-400/10 p-6">
            <p className="text-sm text-cyan-200">API 健康检查</p>
            <p className="mt-2 font-mono text-xs text-cyan-100">{apiBaseUrl}/health</p>
            <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950/60 p-4 text-sm text-cyan-50">
              {JSON.stringify(health ?? { ok: false, status: "loading" }, null, 2)}
            </pre>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
            <p className="text-sm text-stone-300">任务详情</p>
            <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950/70 p-4 text-sm leading-6 text-stone-100">
              {JSON.stringify(
                task ?? {
                  task_id: null,
                  message: "提交表单后会展示任务详情",
                },
                null,
                2,
              )}
            </pre>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
            <p className="text-sm text-stone-300">链路说明</p>
            <ol className="mt-4 space-y-3 text-sm leading-6 text-stone-300">
              <li>1. `POST /tasks` 创建任务</li>
              <li>2. `POST /files/upload` 上传模板或素材，并携带 `task_id`</li>
              <li>3. 后端将文件保存到 `apps/api/uploads/`</li>
              <li>4. `GET /tasks/:task_id` 返回完整任务详情</li>
            </ol>
          </div>
        </section>
      </main>
    </div>
  );
}
