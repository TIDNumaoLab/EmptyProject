// 全画面共通のサイドバー: 権限で表示できる画面へのリンク、利用者名・所属部門、ログアウト
import { NavLink } from "react-router";
import { visibleNav } from "../auth/routes";
import type { Me } from "../types/api";
import styles from "./Sidebar.module.css";

interface Props {
  me: Me;
  onLogout(): void;
}

export default function Sidebar({ me, onLogout }: Props) {
  return (
    <nav className={styles.sidebar} aria-label="メニュー">
      <div className={styles.user}>
        <div className={styles.userName}>{me.name}</div>
        <div className={styles.departments}>
          {me.role === "manager" ? "店長" : me.departments.map((d) => d.name).join("・")}
        </div>
      </div>
      <ul className={styles.links}>
        {visibleNav(me).map((item) => (
          <li key={item.path}>
            {/* end: /orders を /orders/approved で強調しないよう完全一致で判定する */}
            <NavLink to={item.path} end className={({ isActive }) => (isActive ? styles.active : styles.link)}>
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <button type="button" className={styles.logout} onClick={onLogout}>
        ログアウト
      </button>
    </nav>
  );
}
