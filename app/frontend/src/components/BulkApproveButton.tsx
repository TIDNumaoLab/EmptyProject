// チェックした行の一括承認ボタン(警告のある行・未承認でない行はサーバー側で除外される)
import pageStyles from "../styles/page.module.css";

interface Props {
  count: number;
  onClick(): void;
}

export default function BulkApproveButton({ count, onClick }: Props) {
  return (
    <button type="button" className={pageStyles.primary} disabled={count === 0} onClick={onClick}>
      一括承認
    </button>
  );
}
