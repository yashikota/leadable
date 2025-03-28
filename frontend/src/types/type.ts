enum TaskStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

export interface Task {
  _id: string;
  task_id: string;
  status: TaskStatus;
  created_at: string;
  filename: string;
  original_url: string;
  translated_url: string;
  source_lang: string;
  target_lang: string;
  provider: string;
  model_name: string;
  content_type: string;
}

// Define interface for react-select options
export interface SelectOption {
  value: string;
  label: string;
}

// Define interface for available models from API
export interface AvailableModels {
  [provider: string]: string[];
}
