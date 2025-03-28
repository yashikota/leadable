import { ExternalLink, Settings } from "lucide-react";
import { ApiKeyInput } from "./ApiKeyInput";
import type { AvailableModels, SelectOption } from "../types/type";
import { ADDRESS } from "../App";

type LLMSettingsProps = {
  selectedProvider: string;
  selectedModel: string;
  availableModels: AvailableModels;
  isLoadingModels: boolean;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
  apiKeys: Record<string, string>;
  onApiKeyChange: (value: string) => void;
  apiKeySaveStatus: "saved" | "unsaved" | "saving";
  providerNameMap: Record<string, string>;
};

export function LLMSettings({
  selectedProvider,
  selectedModel,
  availableModels,
  isLoadingModels,
  onProviderChange,
  onModelChange,
  apiKeys,
  onApiKeyChange,
  apiKeySaveStatus,
  providerNameMap,
}: LLMSettingsProps) {
  // Get provider options for the dropdown
  const getProviderOptions = (): SelectOption[] => {
    return Object.keys(availableModels).map((providerId) => ({
      value: providerId,
      label: providerNameMap[providerId] || providerId,
    }));
  };

  // Get model options for the dropdown
  const getModelOptions = (): SelectOption[] => {
    if (!availableModels[selectedProvider]) return [];
    return availableModels[selectedProvider].map((modelId) => ({
      value: modelId,
      label: modelId,
    }));
  };

  const ollamaModelManagerUrl = `http://${ADDRESS}:8788`;

  return (
    <div className="collapse collapse-arrow bg-slate-100 mt-8 rounded-box">
      <input type="checkbox" />
      <div className="collapse-title flex justify-between items-center">
        <div className="text-lg font-medium flex items-center gap-2">
          <Settings size={18} />
          LLM設定
        </div>
        {selectedProvider && selectedModel && (
          <div className="text-sm font-medium">
            <span className="badge badge-secondary">
              {providerNameMap[selectedProvider] || selectedProvider}
            </span>{" "}
            / <span className="badge badge-secondary">{selectedModel}</span>
          </div>
        )}
      </div>
      <div className="collapse-content">
        {selectedProvider !== "ollama" && !apiKeys[selectedProvider] && (
          <div className="alert alert-warning py-2 mb-2 text-sm">
            <span>
              APIキーが必要です。下部でAPIキーを設定してください。
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
          <div className="form-control">
            <label htmlFor="provider-select" className="label">
              <span className="label-text">プロバイダー</span>
            </label>
            <select
              id="provider-select"
              className="select select-bordered w-full bg-white"
              value={selectedProvider}
              onChange={(e) => onProviderChange(e.target.value)}
              disabled={isLoadingModels}
            >
              <option disabled value="">
                プロバイダーを選択
              </option>
              {getProviderOptions().map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {isLoadingModels && (
              <div className="mt-2 text-center">
                <span className="loading loading-spinner loading-sm" />
              </div>
            )}
          </div>

          <div className="form-control">
            <label htmlFor="model-select" className="label">
              <span className="label-text">モデル</span>
            </label>
            <select
              id="model-select"
              className="select select-bordered w-full bg-white"
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={isLoadingModels}
            >
              <option disabled value="">
                モデルを選択
              </option>
              {getModelOptions().map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {isLoadingModels && (
              <div className="mt-2 text-center">
                <span className="loading loading-spinner loading-sm" />
              </div>
            )}
          </div>
        </div>

        {selectedProvider === "ollama" && (
          <div className="mt-4">
            <a
              href={ollamaModelManagerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-outline btn-sm flex items-center gap-2"
            >
              <ExternalLink size={16} />
              Ollama モデル管理を開く
            </a>
          </div>
        )}

        {selectedProvider !== "ollama" && (
          <div className="mt-4">
            <ApiKeyInput
              provider={selectedProvider}
              apiKey={apiKeys[selectedProvider]}
              onChange={onApiKeyChange}
              saveStatus={apiKeySaveStatus}
            />
          </div>
        )}
      </div>
    </div>
  );
}
