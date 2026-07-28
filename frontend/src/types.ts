export interface Agent {
  id: string;
  name: string;
  description: string;
  provider: "anthropic" | "openai";
  model: string;
  tools: string[];
  knowledge_file_name: string | null;
  created_at: string;
}

export interface Tool {
  id: string;
  name: string;
  description: string;
}

export interface Run {
  id: string;
  agent_id: string;
  input_message: string;
  status: "running" | "completed" | "failed";
  output_text: string | null;
  created_at: string;
  completed_at: string | null;
}
