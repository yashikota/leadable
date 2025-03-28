enum TaskStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

export type Task = {
  task_id: string;
  filename: string;
  status: TaskStatus;
  created_at: string;
  translated_url?: string;
};

// Define interface for react-select options
export type SelectOption = {
  value: string;
  label: string;
};

// Define interface for available models from API
export type AvailableModels = {
  [provider: string]: string[];
};
