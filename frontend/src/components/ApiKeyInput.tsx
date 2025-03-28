import { type ChangeEvent } from "react";
import { Check, Save } from "lucide-react";

type ApiKeyInputProps = {
  provider: string;
  apiKey: string;
  onChange: (value: string) => void;
  saveStatus: "saved" | "unsaved" | "saving";
};

export function ApiKeyInput({
  apiKey,
  onChange,
  saveStatus,
}: ApiKeyInputProps) {
  const handleApiKeyChange = (e: ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  // Render save status icon
  const renderSaveStatus = () => {
    switch (saveStatus) {
      case "saved":
        return <Check size={16} className="text-success" />;
      case "saving":
        return <div className="loading loading-spinner loading-xs" />;
      case "unsaved":
        return <Save size={16} className="text-warning" />;
    }
  };

  return (
    <div className="form-control w-full">
      <label htmlFor="api-key-input" className="label">
        <span className="label-text">API キー</span>
        <span className="label-text-alt flex items-center gap-1">
          {saveStatus === "saved"
            ? "保存済み"
            : saveStatus === "saving"
              ? "保存中..."
              : "未保存"}
          {renderSaveStatus()}
        </span>
      </label>
      <div className="join w-full">
        <input
          id="api-key-input"
          type="password"
          placeholder="sk-*************************************"
          className="input input-bordered input-primary w-full bg-white"
          value={apiKey || ""}
          onChange={handleApiKeyChange}
        />
      </div>
      <label htmlFor="api-key-input" className="label">
        <span className="label-text-alt text-base-content/70 mt-2">
          APIキーはローカルに保存され、共有されません。
        </span>
      </label>
    </div>
  );
}
