type ApiResponse = {
  message: string;
  service: string;
  ok: boolean;
};

async function getApiMessage() {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/hello`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    return {
      data: (await response.json()) as ApiResponse,
      error: null,
      apiBaseUrl,
    };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "Unknown error",
      apiBaseUrl,
    };
  }
}

export default async function Home() {
  const { data, error, apiBaseUrl } = await getApiMessage();

  return (
    <div className="min-h-screen bg-stone-950 px-6 py-16 text-stone-50">
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur sm:p-10">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.3em] text-emerald-300">
            Acceptance Agent
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">
            Web 已经可以请求 API
          </h1>
          <p className="max-w-2xl text-base leading-7 text-stone-300">
            首页会在服务端渲染时请求 FastAPI 的 <code>/hello</code> 接口，并把结果直接展示出来。
          </p>
        </div>

        <section className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-6">
          <p className="text-sm text-emerald-200">请求地址</p>
          <p className="mt-2 font-mono text-sm text-emerald-100">
            {apiBaseUrl}/hello
          </p>
        </section>

        <section className="rounded-2xl border border-white/10 bg-black/20 p-6">
          <p className="text-sm text-stone-400">接口返回</p>
          <pre className="mt-4 overflow-x-auto rounded-xl bg-black/30 p-4 text-sm leading-6 text-stone-100">
            {JSON.stringify(
              error
                ? { ok: false, error }
                : data,
              null,
              2,
            )}
          </pre>
        </section>
      </main>
    </div>
  );
}
