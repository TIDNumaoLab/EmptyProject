// 警告の表示(詳細設計書「欠損時の扱い」の表示名)
import { WARNING_LABELS } from "../format";
import type { WarningCode } from "../types/api";
import styles from "./Proposals.module.css";

export default function WarningBadge({ code }: { code: WarningCode }) {
  return <span className={styles.warning}>{WARNING_LABELS[code]}</span>;
}
