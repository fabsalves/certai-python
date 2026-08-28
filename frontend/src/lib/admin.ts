export interface OrgListItem {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  user_count: number;
  created_at: string;
}

export interface ModelOption {
  id: string;
  label: string;
  provider: string;
  category: string;
  group: string;
  description: string;
  context?: string | null;
  badge?: string | null;
}

export interface SettingsCatalog {
  version: string;
  chat_models: ModelOption[];
  openai_realtime_models: ModelOption[];
  openai_realtime_voices: ModelOption[];
  groq_transcribe_models: ModelOption[];
  defaults: Record<string, string>;
}

export interface OrgSettings {
  organization_slug: string;
  webhook_base_url: string;
  engine_model: string;
  humanizer_model: string;
  evaluator_model: string;
  groq_transcribe_model: string;
  openai_realtime_model: string;
  openai_realtime_voice: string;
  cinndi_api_url: string;
  cinndi_sender_phone: string;
  whatsapp_invite_template: string;
  whatsapp_invite_voice_template: string;
  whatsapp_invite_use_voice_template: boolean;
  whatsapp_template_lang: string;
  assistant_name: string;
  configured: Record<string, boolean>;
  available: Record<string, boolean>;
  masked_secrets: Record<string, string>;
}

export interface OrgDetail extends OrgListItem {
  settings: OrgSettings;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  whatsapp?: string | null;
  organization_id?: string | null;
  organization_name?: string | null;
}

export const SECRET_FIELDS = [
  { key: "openai_api_key", label: "OpenAI API key", provider: "openai" },
  { key: "groq_api_key", label: "Groq API key", provider: "groq" },
] as const;

export type CatalogListKey =
  | "chat_models"
  | "openai_realtime_models"
  | "openai_realtime_voices"
  | "groq_transcribe_models";

export type ModelSelectIcon =
  | "engine"
  | "humanizer"
  | "evaluator"
  | "transcribe"
  | "realtime"
  | "voice";

export const CHAT_MODEL_SELECTS: Array<{
  key: keyof OrgSettings;
  label: string;
  catalog: CatalogListKey;
  icon: ModelSelectIcon;
}> = [
  { key: "engine_model", label: "Modelo do motor", catalog: "chat_models", icon: "engine" },
  { key: "humanizer_model", label: "Modelo do humanizador", catalog: "chat_models", icon: "humanizer" },
  { key: "evaluator_model", label: "Modelo do avaliador", catalog: "chat_models", icon: "evaluator" },
];

export const AUDIO_MODEL_SELECTS: Array<{
  key: keyof OrgSettings;
  label: string;
  catalog: CatalogListKey;
  icon: ModelSelectIcon;
}> = [
  { key: "groq_transcribe_model", label: "Transcrição Groq", catalog: "groq_transcribe_models", icon: "transcribe" },
  { key: "openai_realtime_model", label: "Modelo Realtime", catalog: "openai_realtime_models", icon: "realtime" },
  { key: "openai_realtime_voice", label: "Voz Realtime", catalog: "openai_realtime_voices", icon: "voice" },
];

export const MODEL_SELECTS = [...CHAT_MODEL_SELECTS, ...AUDIO_MODEL_SELECTS];
