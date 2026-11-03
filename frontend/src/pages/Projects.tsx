import { type FormEvent, type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiUrl, readJsonResponse } from '../lib/api'
import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  ExternalLink,
  FolderKanban,
  GitFork,
  LoaderCircle,
  Plus,
  Printer,
  Sparkles,
  X,
} from 'lucide-react'

type Analysis = {
  architecture_summary: string
  modules: { name: string; purpose: string }[]
  dependencies: { name: string; purpose: string }[]
  risks: { title: string; detail: string; requires_review: boolean }[]
  knowledge_gaps: string[]
  status: string
  observed_facts: string[]
  interpretations: string[]
  verification_items: string[]
  evidence: { path: string; lines: string; excerpt: string }[]
  repository_context: {
    file_count: number
    truncated: boolean
    default_branch: string
  }
}

type Project = {
  id: string
  name: string
  description: string
  repository_url: string
  status: string
  analysis?: Analysis | null
}

const initialForm = { name: '', description: '', repository_url: '' }

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [form, setForm] = useState(initialForm)
  const [showForm, setShowForm] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetch(apiUrl('/api/projects/'))
      .then((response) => readJsonResponse<{ projects: Project[] }>(response))
      .then((data) => setProjects(data.projects))
      .catch(() => setError('Unable to load projects. Check that the backend is running.'))
      .finally(() => setIsLoading(false))
  }, [])

  const updateForm = (field: keyof typeof initialForm, value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  const handleSaveProject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!form.name.trim() || !form.repository_url.trim()) {
      setError('Add a project name and repository URL.')
      return
    }
    setIsSaving(true)
    setError('')
    try {
      const response = await fetch(apiUrl('/api/projects/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description.trim(),
          repository_url: form.repository_url.trim(),
        }),
      })
      const data = await readJsonResponse<{ project: Project }>(response)
      setProjects((current) => [data.project, ...current])
      setForm(initialForm)
      setShowForm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create project.')
    } finally {
      setIsSaving(false)
    }
  }

  const analyze = async (projectId: string) => {
    setAnalyzingId(projectId)
    setError('')
    try {
      const response = await fetch(apiUrl(`/api/projects/${projectId}/analyze`), { method: 'POST' })
      const data = await readJsonResponse<Analysis>(response)
      const analysis = data as Analysis
      setProjects((current) =>
        current.map((project) =>
          project.id === projectId ? { ...project, status: 'analyzed', analysis } : project,
        ),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis could not be started.')
    } finally {
      setAnalyzingId(null)
    }

  }

  const copyReport = async (project: Project) => {
    if (!project.analysis) return
    const report = [
      `CONTINUUM AI — ${project.name}`,
      project.repository_url,
      '',
      'ARCHITECTURE SUMMARY',
      project.analysis.architecture_summary,
      '',
      'OBSERVED FACTS',
      ...project.analysis.observed_facts.map((item) => `- ${item}`),
      '',
      'INTERPRETATIONS',
      ...project.analysis.interpretations.map((item) => `- ${item}`),
      '',
      'VERIFICATION ITEMS',
      ...project.analysis.verification_items.map((item) => `- ${item}`),
    ].join('\n')
    try {
      await navigator.clipboard.writeText(report)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setError('Clipboard access is unavailable. Use Print to save this report instead.')
    }
  }

  return (
    <main className="min-h-screen bg-[var(--surface-page)] text-[var(--text-primary)]">
      <div className="mx-auto max-w-6xl px-6 py-7 lg:px-10">
        <header className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-3 text-sm font-semibold text-[var(--text-primary)]">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--action)] text-white"><GitFork size={16} /></span>
              CONTINUUM <span className="text-violet-300">AI</span>
            </Link>
            <span className="hidden h-5 w-px bg-[var(--border-subtle)] sm:block" />
            <Link to="/" className="hidden items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-white sm:flex">
              <ArrowLeft size={16} /> Overview
            </Link>
          </div>
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">Workspace</span>
        </header>

        <div className="flex flex-wrap items-end justify-between gap-5 py-12">
          <div>
            <p className="mb-3 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--text-secondary)]">Knowledge workspace</p>
            <h1 className="text-4xl font-semibold tracking-[-0.03em]">Projects</h1>
            <p className="mt-3 max-w-xl text-[var(--text-secondary)]">
              Connect repositories and turn scattered engineering context into reviewable handovers.
            </p>
          </div>
          <button
            type="button"
            onClick={() => { setError(''); setShowForm(true) }}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--action)] px-4 py-2.5 font-semibold text-white hover:bg-[var(--action-hover)]"
          >
            <Plus size={17} /> Connect repository
          </button>
        </div>

        {error && (
          <p role="alert" className="mb-6 rounded-lg border border-[#d9b8b8] bg-[#fbf3f3] px-4 py-3 text-sm text-[var(--error)]">
            {error}
          </p>
        )}

        {showForm && (
          <form onSubmit={handleSaveProject} className="mb-8 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-6">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold">Connect a repository</h2>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">Analysis remains evidence-first and reviewable.</p>
              </div>
              <button type="button" onClick={() => setShowForm(false)} aria-label="Close form" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X size={19} />
              </button>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <Field label="Project name" htmlFor="project-name">
                <input id="project-name" required value={form.name} onChange={(event) => updateForm('name', event.target.value)} placeholder="e.g. Payments platform" maxLength={100} className="field-control" />
              </Field>
              <Field label="Repository URL" htmlFor="repository-url">
                <input id="repository-url" required type="url" value={form.repository_url} onChange={(event) => updateForm('repository_url', event.target.value)} placeholder="https://github.com/org/repository" className="field-control" />
              </Field>
              <Field label="Transition context (optional)" htmlFor="description" wide>
                <textarea id="description" value={form.description} onChange={(event) => updateForm('description', event.target.value)} placeholder="What should the next engineer know?" rows={3} className="field-control resize-y" />
              </Field>
            </div>
            <button type="submit" disabled={isSaving} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[var(--action)] px-5 py-3 font-semibold text-white hover:bg-[var(--action-hover)] disabled:cursor-not-allowed disabled:opacity-50">
              {isSaving && <LoaderCircle size={16} className="animate-spin" />}
              {isSaving ? 'Connecting...' : 'Connect project'}
            </button>
          </form>
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 py-16 text-sm text-[var(--text-secondary)]"><LoaderCircle size={17} className="animate-spin" /> Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border-subtle)] bg-[var(--surface-card)] px-6 py-20 text-center">
            <FolderKanban size={36} className="mx-auto mb-4 text-[var(--text-secondary)]" />
            <h2 className="text-xl font-semibold">No projects connected</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-[var(--text-secondary)]">Connect a repository to reconstruct its architecture, risks, and ownership context.</p>
          </div>
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">
            {projects.map((project) => (
              <article key={project.id} className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-card)] p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-secondary)]"><GitFork size={20} /></div>
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold">{project.name}</h2>
                      <a href={project.repository_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex max-w-full items-center gap-1 truncate text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                        {project.repository_url}<ExternalLink size={13} className="shrink-0" />
                      </a>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium capitalize ${project.status === 'analyzed' ? 'bg-[#edf5f1] text-[var(--success)]' : 'bg-[var(--surface-muted)] text-[var(--text-secondary)]'}`}>
                    {project.status}
                  </span>
                </div>
                <p className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">{project.description || 'No transition context added yet.'}</p>
                {project.analysis ? (
                  <div className="mt-6 space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-[var(--success)]"><CheckCircle2 size={16} /> Analysis ready for review</div>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" onClick={() => copyReport(project)} className="inline-flex items-center gap-2 rounded-md border border-[var(--border-subtle)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"><Copy size={14} /> {copied ? 'Copied report' : 'Copy report'}</button>
                      <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-md border border-[var(--border-subtle)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"><Printer size={14} /> Print</button>
                    </div>
                    {project.analysis.repository_context && (
                      <p className="text-xs text-[var(--text-secondary)]">
                        Indexed {project.analysis.repository_context.file_count} text files on the{' '}
                        <span className="font-medium text-[var(--text-primary)]">{project.analysis.repository_context.default_branch}</span>{' '}
                        branch{project.analysis.repository_context.truncated ? ' (capped at the ingestion limit)' : ''}.
                      </p>
                    )}
                    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-3">
                      <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Architecture summary</p>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-primary)]">{project.analysis.architecture_summary}</p>
                    </div>
                    {(project.analysis.modules.length > 0 || project.analysis.dependencies.length > 0 || project.analysis.risks.length > 0) && (
                      <div className="grid gap-3 sm:grid-cols-3">
                        <Insight label="Modules" items={project.analysis.modules.map((item) => `${item.name}: ${item.purpose}`)} tone="neutral" />
                        <Insight label="Dependencies" items={project.analysis.dependencies.map((item) => `${item.name}: ${item.purpose}`)} tone="neutral" />
                        <Insight label="Risks" items={project.analysis.risks.map((item) => `${item.title}: ${item.detail}`)} tone="warning" />
                      </div>
                    )}
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Insight label="Observed" items={project.analysis.observed_facts} tone="neutral" />
                      <Insight label="Interpreted" items={project.analysis.interpretations} tone="neutral" />
                      <Insight label="Verify" items={project.analysis.verification_items} tone="warning" />
                    </div>
                    {project.analysis.evidence[0]?.path && <details className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)]">
                      <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-[var(--text-secondary)]">
                        View source evidence ({project.analysis.evidence.length} files)
                      </summary>
                      <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
                        {project.analysis.evidence.slice(0, 5).map((evidence) => (
                          <div key={`${evidence.path}-${evidence.lines}`} className="rounded-md bg-[var(--surface-card)] p-3">
                            <p className="text-xs font-semibold text-[var(--text-primary)]">{evidence.path} <span className="font-normal text-[var(--text-secondary)]">({evidence.lines})</span></p>
                            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] leading-5 text-[var(--text-secondary)]">{evidence.excerpt}</pre>
                          </div>
                        ))}
                      </div>
                    </details>}
                  </div>
                ) : (
                  <button type="button" onClick={() => analyze(project.id)} disabled={analyzingId === project.id} className="mt-6 inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] px-4 py-2.5 text-sm font-semibold text-[var(--action)] hover:bg-[var(--surface-muted)] disabled:opacity-50">
                    {analyzingId === project.id ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}
                    {analyzingId === project.id ? 'Reconstructing...' : 'Reconstruct knowledge'}
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}

function Field({ label, htmlFor, wide = false, children }: { label: string; htmlFor: string; wide?: boolean; children: ReactNode }) {
  return <label htmlFor={htmlFor} className={`text-sm text-[var(--text-secondary)] ${wide ? 'md:col-span-2' : ''}`}>{label}{children}</label>
}

function Insight({ label, items, tone }: { label: string; items: string[]; tone: 'neutral' | 'warning' }) {
  return (
    <div className={`rounded-lg border p-3 ${tone === 'warning' ? 'border-amber-400/20 bg-amber-400/10' : 'border-[var(--border-subtle)] bg-[var(--surface-muted)]'}`}>
      <p className={`mb-2 text-xs font-bold uppercase tracking-wider ${tone === 'warning' ? 'text-[var(--warning)]' : 'text-[var(--text-secondary)]'}`}>{label}</p>
      <p className="line-clamp-4 text-xs leading-5 text-[var(--text-primary)]">{items[0]}</p>
    </div>
  )
}
