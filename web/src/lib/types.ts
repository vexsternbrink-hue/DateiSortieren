export type ActionKind = "move" | "delete" | "compress";
export type ActionStatus =
  | "proposed"
  | "approved"
  | "rejected"
  | "applied"
  | "skipped"
  | "failed"
  | "undo_requested"
  | "undone";

export interface ActionRow {
  id: string;
  user_id: string;
  agent_id: string | null;
  batch_id: string | null;
  kind: ActionKind;
  status: ActionStatus;
  src_path: string;
  dst_path: string | null;
  reason: string | null;
  confidence: number | null;
  category: string | null;
  tags: string[];
  details: Record<string, unknown> & {
    classification?: {
      category?: string;
      doc_type?: string;
      vendor?: string | null;
      date?: string | null;
      amount?: number | null;
      summary?: string;
      source?: string;
    };
    duplicate_of?: string;
    match?: string;
    cleanup?: string;
    size?: number;
    size_before?: number;
    size_after?: number;
    size_after_estimate?: number;
    savings_percent?: number;
  };
  error: string | null;
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  undone_at: string | null;
}

export interface RuleMatch {
  extensions?: string[];
  name_contains?: string[];
  name_regex?: string;
  content_keywords?: string[];
  path_contains?: string;
  category_is?: string;
  min_size_kb?: number | null;
  max_size_kb?: number | null;
}

export interface RuleRow {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  priority: number;
  enabled: boolean;
  match: RuleMatch;
  action: "move" | "ignore" | "delete";
  target: string | null;
  rename_template: string | null;
  tags: string[];
  created_at: string;
}

export interface SafelistRow {
  id: string;
  kind: "path" | "glob" | "extension" | "tag";
  value: string;
  note: string | null;
  created_at: string;
}

export interface AgentRow {
  id: string;
  name: string;
  token_prefix: string;
  hostname: string | null;
  platform: string | null;
  version: string | null;
  info: Record<string, unknown>;
  last_seen_at: string | null;
  scan_requested_at: string | null;
  created_at: string;
}

export interface LogRow {
  id: number;
  agent_id: string | null;
  level: "debug" | "info" | "warning" | "error";
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ProfileSettings {
  dry_run: boolean;
  auto_apply_min_confidence: number;
  rename_template: string;
  organize_template: string;
  ai_instructions: string;
  installer_max_age_days: number;
  media_enabled: boolean;
  duplicates_enabled: boolean;
  cleanup_enabled: boolean;
  rename_enabled: boolean;
}

export interface ProfileRow {
  id: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  settings: Partial<ProfileSettings>;
}

export const DEFAULT_SETTINGS: ProfileSettings = {
  dry_run: true,
  auto_apply_min_confidence: 0.85,
  rename_template: "{date}_{vendor}_{doc_type}_{amount}",
  organize_template: "{category}/{year}",
  ai_instructions: "",
  installer_max_age_days: 14,
  media_enabled: false,
  duplicates_enabled: true,
  cleanup_enabled: true,
  rename_enabled: true,
};
