// 確認ダイアログ(削除や、警告付きの提案の承認などで使う)
interface Props {
  open: boolean;
  message: string;
  onConfirm(): void;
  onCancel(): void;
}

export default function ConfirmDialog({ open, message, onConfirm, onCancel }: Props) {
  if (!open) {
    return null;
  }
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      <div role="dialog" aria-modal="true" style={{ background: "#fff", padding: 24, borderRadius: 8, minWidth: 360 }}>
        <p style={{ marginTop: 0 }}>{message}</p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" onClick={onCancel}>
            いいえ
          </button>
          <button type="button" onClick={onConfirm} autoFocus>
            はい
          </button>
        </div>
      </div>
    </div>
  );
}
