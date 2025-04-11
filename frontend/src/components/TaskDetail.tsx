import {
  ArrowLeft,
  FileText,
  SquareArrowOutUpRight,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { API_URL } from "../App";
import type { Task } from "../types/type";

// ステータスの日本語表示を取得
const getStatusLabel = (status?: string): string => {
  if (!status) return "不明";
  switch (status) {
    case "pending":
      return "待機中";
    case "processing":
      return "処理中";
    case "completed":
      return "完了";
    case "failed":
      return "失敗";
    default:
      return status;
  }
};

// ステータスに応じたバッジのスタイルを取得
const getStatusBadgeClass = (status?: string): string => {
  if (!status) return "badge-neutral";
  switch (status) {
    case "pending":
      return "badge-warning";
    case "processing":
      return "badge-info";
    case "completed":
      return "badge-primary";
    case "failed":
      return "badge-error";
    default:
      return "badge-neutral";
  }
};

export function TaskDetail() {
  const { task_id } = useParams<{ task_id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchTaskDetails = async () => {
      setLoading(true);
      try {
        const response = await fetch(`${API_URL}/task/${task_id}`);
        const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");

        if (errorMessage) {
          throw new Error(errorMessage);
        }

        if (!response.ok) {
          if (response.status === 503) {
            throw new Error(
              "バックエンドサービスが利用できません。しばらく待ってから再試行してください。",
            );
          }
          if (response.status === 404) {
            throw new Error("タスクが見つかりません");
          }
          throw new Error(`タスクの取得に失敗しました (${response.status})`);
        }

        const data = await response.json();
        setTask(data);
      } catch (err) {
        console.error("タスク詳細の取得に失敗しました:", err);
        if (err instanceof Error) {
          if (err.message.includes("Failed to fetch")) {
            setError(
              "バックエンドサーバーに接続できません。サーバーが起動しているか確認してください。",
            );
          } else {
            setError(err.message);
          }
        } else {
          setError("タスクの取得に失敗しました");
        }
      } finally {
        setLoading(false);
      }
    };

    if (task_id) {
      fetchTaskDetails();
    }
  }, [task_id]);

  const handleDeleteTask = () => {
    setIsDeleting(true);
    fetch(`${API_URL}/task/${task_id}`, {
      method: "DELETE",
    })
      .then((response) => {
        // Check for error header
        const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
        if (errorMessage) {
          throw new Error(errorMessage);
        }

        if (!response.ok) {
          if (response.status === 503) {
            throw new Error(
              "バックエンドサービスが利用できません。しばらく待ってから再試行してください。",
            );
          }
          if (response.status === 404) {
            throw new Error("タスクが見つかりません");
          }
          throw new Error(`タスクの削除に失敗しました (${response.status})`);
        }

        navigate("/");
      })
      .catch((err) => {
        console.error("タスクの削除に失敗しました:", err);
        if (err instanceof Error) {
          if (err.message.includes("Failed to fetch")) {
            setError(
              "バックエンドサーバーに接続できません。サーバーが起動しているか確認してください。",
            );
          } else {
            setError(err.message);
          }
        } else {
          setError("タスクの削除に失敗しました");
        }
      })
      .finally(() => {
        setIsDeleting(false);
      });
  };

  if (loading || error || !task) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <div className="flex justify-between items-center mb-6">
          <Link to="/" className="btn btn-sm btn-outline">
            <ArrowLeft size={18} className="mr-2" /> 一覧に戻る
          </Link>
        </div>
        <div className="flex justify-center items-center h-64">
          <span className="loading loading-spinner loading-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="flex justify-between items-center mb-6">
        <Link to="/" className="btn btn-sm btn-outline">
          <ArrowLeft size={18} className="mr-2" /> 一覧に戻る
        </Link>
        <button
          className="btn btn-sm btn-error"
          onClick={() => {
            (
              document.getElementById("delete-modal") as HTMLDialogElement
            ).showModal();
          }}
          disabled={isDeleting}
        >
          <Trash2 size={18} className="mr-2" />
          削除
        </button>
      </div>

      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <div className="flex items-center mb-4">
            <FileText size={24} className="mr-2 text-primary" />
            <h2 className="card-title text-2xl font-bold">{task.filename}</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div className="form-control">
              <label className="label" htmlFor="task-id">
                <span className="label-text">タスクID</span>
              </label>
              <input
                id="task-id"
                type="text"
                readOnly
                value={task.task_id}
                className="input input-bordered"
              />
            </div>

            <div className="form-control">
              <label className="label" htmlFor="task-status">
                <span className="label-text">ステータス</span>
              </label>
              <div id="task-status">
                <span className={`badge ${getStatusBadgeClass(task.status)}`}>
                  {getStatusLabel(task.status)}
                </span>
              </div>
            </div>

            <div className="form-control">
              <label className="label" htmlFor="task-created-at">
                <span className="label-text">作成日時</span>
              </label>
              <input
                id="task-created-at"
                type="text"
                readOnly
                value={new Date(task.created_at).toLocaleString()}
                className="input input-bordered"
              />
            </div>
          </div>

          {task.translated_url && task.status === "completed" && (
            <div className="card-actions justify-end mt-6">
              <a
                href={task.translated_url}
                className="btn btn-primary"
                target="_blank"
                rel="noopener noreferrer"
              >
                <SquareArrowOutUpRight size={18} className="mr-2" />
                翻訳されたファイルを開く
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation modal */}
      <dialog id="delete-modal" className="modal modal-bottom sm:modal-middle">
        <div className="modal-box">
          <h3 className="font-bold text-lg">確認</h3>
          <p className="py-4">
            「{task.filename}」を削除してもよろしいですか？
          </p>
          <div className="modal-action">
            <form method="dialog">
              <button className="btn mr-2" disabled={isDeleting}>
                キャンセル
              </button>
            </form>
            <button
              type="button"
              className="btn btn-error"
              onClick={handleDeleteTask}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <span className="loading loading-spinner loading-xs mr-2" />
                  削除中...
                </>
              ) : (
                "削除する"
              )}
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
}
