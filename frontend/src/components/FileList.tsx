import { SquareArrowOutUpRight, Trash2 } from "lucide-react";
import type { Task } from "../types/type";

type FileListProps = {
  tasks: Task[];
  onDeleteTask: (taskId: string) => void;
};

export function FileList({ tasks, onDeleteTask }: FileListProps) {
  // ステータスの日本語表示を取得
  const getStatusLabel = (status: string): string => {
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
  const getStatusBadgeClass = (status: string): string => {
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

  if (tasks.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h2 className="text-xl font-bold mb-4">ファイル一覧</h2>
      <div className="overflow-x-auto">
        <table className="table w-full">
          <thead>
            <tr>
              <th>ファイル名</th>
              <th>ステータス</th>
              <th>作成日時</th>
              <th className="text-right">アクション</th>
            </tr>
          </thead>
          <tbody>
            {tasks
              .slice()
              .sort(
                (a, b) =>
                  new Date(b.created_at).getTime() -
                  new Date(a.created_at).getTime(),
              )
              .map((task: Task) => (
                <tr key={task.task_id} className="hover">
                  <td className="max-w-xs truncate">{task.filename}</td>
                  <td>
                    <span
                      className={`badge ${getStatusBadgeClass(task.status)}`}
                    >
                      {getStatusLabel(task.status)}
                    </span>
                  </td>
                  <td>{new Date(task.created_at).toLocaleString()}</td>
                  <td className="text-right">
                    <div className="join">
                      {task.status === "completed" ? (
                        <a
                          href={task.translated_url}
                          className="btn btn-sm join-item hover:bg-blue-200 border-none"
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="開く"
                        >
                          <SquareArrowOutUpRight size={18} />
                        </a>
                      ) : (
                        <button
                          className="btn btn-sm join-item hover:bg-blue-200 border-none opacity-50 cursor-not-allowed"
                          disabled
                          aria-label="準備中"
                        >
                          <SquareArrowOutUpRight size={18} />
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-sm join-item hover:bg-red-200 border-none"
                        onClick={() => {
                          (
                            document.getElementById(
                              `delete-modal-${task.task_id}`,
                            ) as HTMLDialogElement
                          ).showModal();
                          setTimeout(() => {
                            const modal = document.getElementById(
                              `delete-modal-${task.task_id}`,
                            ) as HTMLDialogElement;
                            if (modal.open) {
                              modal.showModal();
                            }
                          }, 0);
                        }}
                        aria-label="削除"
                      >
                        <Trash2 size={18} />
                      </button>

                      {/* Delete confirmation modal */}
                      <dialog
                        id={`delete-modal-${task.task_id}`}
                        className="modal modal-bottom sm:modal-middle"
                      >
                        <div className="modal-box">
                          <p className="py-4 text-xl">
                            「{task.filename}」を削除してもよろしいですか？
                          </p>
                          <div className="modal-action">
                            <form method="dialog">
                              <button className="btn mr-2">
                                キャンセル
                              </button>
                            </form>
                            <button
                              type="button"
                              className="btn btn-error"
                              onClick={() => {
                                onDeleteTask(task.task_id);
                                document.getElementById(
                                  `delete-modal-${task.task_id}`,
                                );
                              }}
                            >
                              削除する
                            </button>
                          </div>
                        </div>
                      </dialog>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
