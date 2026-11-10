/** TypeScript interfaces matching agy-automation FastAPI schemas */

export interface Project {
  id: string;
  name: string;
  path: string;
  git_remote?: string | null;
  git_branch?: string | null;
  is_active: boolean;
  has_custom_instructions: boolean;
  instructions_filename?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export interface Issue {
  number: number;
  title: string;
  body: string;
  author: string;
  labels: string[];
  comments_count: number;
  created_at: string;
  url: string;
}

export interface IssueListResponse {
  issues: Issue[];
  total: number;
  project_id: string;
}

export interface IssueCreateRequest {
  title: string;
  body: string;
}

export type RunStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'AWAITING_REVIEW'
  | 'COMPLETED'
  | 'FAILED'
  | 'ABORTED';

export interface Run {
  id: string;
  project_id: string;
  target_type: 'issue' | 'session';
  target_id: string;
  status: RunStatus;
  worktree_name?: string | null;
  container_name?: string | null;
  branch_name?: string | null;
  base_branch: string;
  conversation_id?: string | null;
  log_dir?: string | null;
  auto_approve: boolean;
  engine: string;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
}

export interface RunListResponse {
  runs: Run[];
  total: number;
}

export interface RunCreateRequest {
  project_id?: string;
  target_type?: 'issue' | 'session';
  target_id: string;
  auto_approve?: boolean;
  engine?: string;
  conversation_id?: string;
}

export interface RunDiffResponse {
  run_id: string;
  worktree_name?: string | null;
  container_name?: string | null;
  branch_name?: string | null;
  base_branch: string;
  diff_stat: string;
  diff_snippet: string;
  commits: string[];
  summary?: string | null;
}

export interface RunReviewRequest {
  approved: boolean;
  push?: boolean;
}

export interface RunReviewResponse {
  run_id: string;
  status: string;
  merged: boolean;
  pushed: boolean;
  message: string;
}

export interface QuotaBucket {
  id: string;
  name: string;
  description?: string | null;
  window: string;
  remaining_fraction: number;
  remaining_percent: number;
  reset_time?: string | null;
}

export interface QuotaGroup {
  name: string;
  description?: string | null;
  buckets: QuotaBucket[];
}

export interface QuotaResponse {
  description?: string | null;
  groups: QuotaGroup[];
  cached: boolean;
  updated_at: string;
  error?: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_call?: string | null;
}

export interface DraftIssue {
  title: string;
  body: string;
}

export interface ChatSession {
  session_id: string;
  project_id: string;
  status: 'ACTIVE' | 'TERMINATED' | 'CONVERTED';
  session_slug: string;
  worktree_name: string;
  branch_name: string;
  conversation_id?: string | null;
  messages: ChatMessage[];
  draft_issue?: DraftIssue | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionCreateRequest {
  project_id?: string;
  initial_prompt?: string;
}

export interface CreateAndRunRequest {
  title: string;
  body: string;
  auto_approve?: boolean;
  engine?: string;
}

export interface CreateAndRunResponse {
  session_id: string;
  issue_number: number;
  issue_url: string;
  run_id: string;
  message: string;
}

export interface WorktreeStorageItem {
  name: string;
  path: string;
  size_bytes: number;
  size_human: string;
  is_orphaned: boolean;
  run_id?: string | null;
  branch_name?: string | null;
}

export interface StorageInfoResponse {
  project_id: string;
  project_name: string;
  worktrees_total_count: number;
  worktrees_orphaned_count: number;
  worktrees_total_bytes: number;
  worktrees_total_human: string;
  runs_logs_bytes: number;
  runs_logs_human: string;
  containers_count: number;
  items: WorktreeStorageItem[];
}

export interface StoragePruneResponse {
  pruned_worktrees: string[];
  reclaimed_bytes: number;
  reclaimed_human: string;
  pruned_containers: number;
  message: string;
}
