export interface Agent {
  id: string;
  name: string;
  role: string;
  provider: "anthropic" | "openai";
  model: string;
  skills: string[];
  tools: string[];
  knowledge_file_name: string | null;
  created_at: string;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
}

export interface Tool extends Skill {
  enabled: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_name: string | null;
  seq: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  last_message_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Turn {
  user_message: Message;
  assistant_message: Message;
  tool_messages: Message[];
  conversation_title: string;
}

export interface Run {
  id: string;
  agent_id: string;
  conversation_id: string | null;
  input_message: string;
  status: "running" | "completed" | "failed";
  output_text: string | null;
  created_at: string;
  completed_at: string | null;
}
