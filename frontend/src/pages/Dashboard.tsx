import { type ReactNode, useEffect, useState } from 'react'
import {
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  FileText,
  FolderKanban,
  GitBranch,
  GitFork,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiUrl } from '../lib/api'

type Project = {
  id: string
  name: string
  description: string
  repository_url: string
  status: string
  analysis?: { repository_context?: { file_count: number } }
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetch(apiUrl('/api/projects/'))
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load projects')
        return response.json()
      })
      .then((data) => setProjects(data.projects))
      .catch(() => setProjects([]))
      .finally(() => setIsLoading(false))
  }, [])

  const analyzed = projects.filter((project) => project.status === 'analyzed').length

  return (
    <main className="min-h-screen bg-[var(--surface-page)] text-[var(--text-primary)]">
      <nav className="mx-auto flex max-w-7xl items-center justify-between border-b border-[var(--border-subtle)] px-6 py-5 lg:px-10">
        <Link to="/" className="flex items-center gap-3" aria-label="Continuum AI home">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--action)] text-white shadow-lg shadow-violet-950/30"><GitBranch size={18} /></span>
          <span className="font-semibold tracking-tight">CONTINUUM <span className="text-violet-300">AI</span></span>
        </Link>
        <div className="hidden items-center gap-7 text-sm text-[var(--text-secondary)] md:flex">
          <a href="#workflow" className="hover:text-white">How it works</a>
          <a href="#capabilities" className="hover:text-white">Capabilities</a>
          <Link to="/projects" className="rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-[var(--text-primary)] hover:bg-[var(--surface-muted)]">Workspace</Link>
        </div>
        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">IdeaOrbit</span>
      </nav>

      <div className="mx-auto max-w-7xl px-6 lg:px-10">
        <section className="grid items-center gap-12 border-b border-[var(--border-subtle)] py-20 lg:grid-cols-[1.05fr_.95fr] lg:py-28">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-400/10 px-3 py-1.5 text-xs font-medium text-violet-200">
              <Sparkles size={14} /> Engineering knowledge, reconstructed
            </div>
            <h1 className="max-w-3xl text-5xl font-semibold leading-[1.03] tracking-[-0.045em] sm:text-7xl">
              Your codebase has a memory. <span className="text-violet-300">Make it accessible.</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-[var(--text-secondary)]">
              Continuum turns repository evidence into an accurate, reviewable handover for the engineer who inherits it next.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link to="/projects" className="inline-flex items-center gap-2 rounded-lg bg-[var(--action)] px-5 py-3.5 font-semibold text-white shadow-lg shadow-violet-950/30 hover:bg-[var(--action-hover)]">
                Start reconstructing <ArrowUpRight size={17} />
              </Link>
              <a href="#workflow" className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-5 py-3.5 font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)]">
                Explore how it works <ChevronRight size={17} />
              </a>
            </div>
          </div>
          <ProductPreview projects={projects} isLoading={isLoading} />
        </section>

        <section className="grid gap-3 border-b border-[var(--border-subtle)] py-8 sm:grid-cols-3">
          <Metric icon={FolderKanban} label="Connected projects" value={isLoading ? '—' : projects.length} />
          <Metric icon={BrainCircuit} label="Completed reconstructions" value={isLoading ? '—' : analyzed} />
          <Metric icon={FileText} label="Handover reports" value="—" note="Not yet available" />
        </section>

        <section id="workflow" className="scroll-mt-8 py-20">
          <Eyebrow>From code to continuity</Eyebrow>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">Transfer understanding, not just documentation.</h2>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            <Step number="01" title="Connect GitHub" text="Bring in the repository and the context the next owner needs." icon={GitFork} />
            <Step number="02" title="Reconstruct knowledge" text="Ground architecture, dependencies, and risks in source evidence." icon={BrainCircuit} />
            <Step number="03" title="Transfer understanding" text="Give the next engineer a clear, reviewable starting point." icon={ShieldCheck} />
          </div>
        </section>

        <section id="capabilities" className="scroll-mt-8 border-t border-[var(--border-subtle)] py-20">
          <div className="grid gap-10 lg:grid-cols-[.8fr_1.2fr]">
            <div><Eyebrow>Built for trust</Eyebrow><h2 className="mt-3 text-3xl font-semibold tracking-tight">Evidence before confidence.</h2><p className="mt-4 leading-7 text-[var(--text-secondary)]">Every reconstruction keeps observed repository facts separate from interpretations and open questions.</p></div>
            <div className="grid gap-3 sm:grid-cols-2"><Capability icon={CheckCircle2} title="Source-grounded" text="Real files, paths, and line-numbered excerpts stay attached to the work." /><Capability icon={ShieldCheck} title="Reviewable by design" text="Unsupported conclusions are surfaced as verification items, not hidden as facts." /><Capability icon={GitBranch} title="Repository-aware" text="Source files and dependency manifests form the analysis context." /><Capability icon={FileText} title="Handover-ready" text="A focused knowledge workspace for the person taking ownership next." /></div>
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-[var(--border-subtle)] py-7 text-xs text-[var(--text-muted)]"><span>CONTINUUM AI · IdeaOrbit</span><span>Engineering continuity, made visible.</span></footer>
      </div>
    </main>
  )
}

function ProductPreview({ projects, isLoading }: { projects: Project[]; isLoading: boolean }) {
  const project = projects[0]
  return <div className="relative"><div className="absolute -inset-8 rounded-full bg-violet-500/10 blur-3xl" /><div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#12111b] shadow-2xl shadow-black/40"><div className="flex items-center gap-1.5 border-b border-white/10 px-5 py-4"><span className="h-2 w-2 rounded-full bg-white/20" /><span className="h-2 w-2 rounded-full bg-white/20" /><span className="h-2 w-2 rounded-full bg-white/20" /><span className="ml-3 text-xs text-white/40">continuum / workspace</span></div><div className="grid min-h-[310px] grid-cols-[150px_1fr]"><div className="border-r border-white/10 p-4"><div className="mb-8 text-xs font-semibold text-violet-200">CONTINUUM AI</div><div className="space-y-3 text-xs text-white/40"><div className="rounded-md bg-white/10 px-2 py-2 text-white/80">Overview</div><div className="px-2">Projects</div><div className="px-2">Evidence</div></div></div><div className="p-6"><div className="text-xs uppercase tracking-widest text-white/35">Knowledge workspace</div><div className="mt-3 text-2xl font-semibold">{isLoading ? 'Loading context...' : project?.name || 'Your next handover'}</div><div className="mt-2 text-sm leading-6 text-white/45">{project ? 'Repository context is ready to turn into a reviewable reconstruction.' : 'Connect a repository to see architecture, risks, and ownership context.'}</div><div className="mt-8 grid grid-cols-3 gap-2">{['Observed', 'Interpreted', 'Verify'].map((label, index) => <div key={label} className="rounded-lg border border-white/10 bg-white/[.03] p-3"><div className={`mb-4 h-1 w-6 rounded-full ${index === 2 ? 'bg-amber-300/70' : 'bg-violet-300/70'}`} /><div className="text-xs text-white/60">{label}</div><div className="mt-2 h-2 w-14 rounded bg-white/10" /></div>)}</div></div></div></div></div>
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof FolderKanban; label: string; value: number | string; note?: string }) {
  return <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5"><Icon size={19} className="mb-7 text-violet-300" /><p className="text-sm text-[var(--text-secondary)]">{label}</p><p className="mt-1 text-3xl font-semibold">{value}</p>{note && <p className="mt-1 text-xs text-[var(--text-muted)]">{note}</p>}</div>
}

function Step({ number, title, text, icon: Icon }: { number: string; title: string; text: string; icon: typeof GitBranch }) {
  return <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5 transition-colors hover:border-violet-400/30"><div className="flex items-center justify-between text-violet-300"><Icon size={20} /><span className="text-xs font-semibold tracking-widest text-[var(--text-muted)]">{number}</span></div><h3 className="mt-10 font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{text}</p></div>
}

function Capability({ icon: Icon, title, text }: { icon: typeof CheckCircle2; title: string; text: string }) {
  return <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-5"><Icon size={19} className="text-violet-300" /><h3 className="mt-5 font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{text}</p></div>
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-300">{children}</p>
}
