// 画面上部に出すエラー文言(API 呼び出しの失敗など)
interface Props {
  message: string | null;
}

export default function ErrorBanner({ message }: Props) {
  if (!message) {
    return null;
  }
  return (
    <div
      role="alert"
      style={{ background: "#fdecea", color: "#8a1c1c", padding: "10px 16px", borderRadius: 4, marginBottom: 16 }}
    >
      {message}
    </div>
  );
}
