export interface Task {
  _id: string;
  task_id: string;
  timestamp: string;
  original_filename: string;
  original_file_url: string;
  translated_filename: string;
  translated_file_url: string;
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
