"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

type HealthResponse = {
  ok: boolean;
  service: string;
  status: string;
};

type Task = {
  id: string;
  title: string;
  description: string | null;
  status: "pending";
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const router = useRouter();
  const initializedRef = useRef(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initializedRef.current) {
      return;
    }
    initializedRef.current = true;

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
    void refreshTaskList();

    return () => {
      active = false;
    };
  }, []);

  async function refreshTaskList() {
    setLoadingTasks(true);

    try {
      const response = await fetch(`${apiBaseUrl}/tasks`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Fetch task list failed with status ${response.status}`);
      }

      const data = (await response.json()) as Task[];
      setTasks(data);
    } catch (taskError) {
      setError(
        taskError instanceof Error ? taskError.message : "Failed to fetch task list",
      );
    } finally {
      setLoadingTasks(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

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
      await refreshTaskList();
      router.push(`/tasks/${createdTask.id}`);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Request failed",
      );
    } finally {
      setSubmitting(false);
    }
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
              创建任务并进入详情页
            </h1>
            <p className="max-w-2xl text-base leading-7 text-stone-300">
              先创建任务，再在详情页上传多个文件、设模板、解析模板并查看字段列表。
            </p>
          </div>

          <form className="mt-10 space-y-6" onSubmit={handleSubmit}>
            <div className="grid gap-6 md:grid-cols-1">
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
                {submitting ? "创建中..." : "创建任务"}
              </button>
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
            <div className="flex items-center justify-between gap-4">
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
            <div className="mt-4 space-y-2">
              {tasks.length ? (
                tasks.map((task) => (
                  <Link
                    key={task.id}
                    className="block rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-stone-100 transition hover:border-cyan-300/30"
                    href={`/tasks/${task.id}`}
                  >
                    <p className="font-medium">{task.title}</p>
                    <p className="mt-1 font-mono text-xs text-stone-400">{task.id}</p>
                  </Link>
                ))
              ) : (
                <p className="rounded-xl border border-dashed border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-stone-400">
                  暂无任务，先创建一个任务开始流程。
                </p>
              )}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
            <p className="text-sm text-stone-300">链路说明</p>
            <ol className="mt-4 space-y-3 text-sm leading-6 text-stone-300">
              <li>1. `POST /tasks` 创建任务</li>
              <li>2. 进入任务详情，`POST /files/upload` 一次上传多个文件</li>
              <li>3. 文件列表中设置模板与素材</li>
              <li>4. 对模板执行解析并查看字段列表</li>
            </ol>
          </div>
        </section>
      </main>
    </div>
  );
}
