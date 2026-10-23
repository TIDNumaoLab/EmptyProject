// 画面の一覧(基本設計書「画面構成」)と、権限による表示の判定
import type { Me } from "../types/api";

export interface NavItem {
  path: string;
  label: string;
  managerOnly: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { path: "/orders", label: "発注", managerOnly: false },
  { path: "/production", label: "製造計画", managerOnly: false },
  { path: "/orders/approved", label: "承認済み発注リスト", managerOnly: false },
  { path: "/imports", label: "データ取込", managerOnly: false },
  { path: "/inventory", label: "在庫入力", managerOnly: false },
  { path: "/promotions", label: "特売・チラシ", managerOnly: false },
  { path: "/calendar", label: "カレンダー", managerOnly: true },
  { path: "/settings", label: "設定", managerOnly: true },
  { path: "/review", label: "予測と実績の比較", managerOnly: false },
];

export function visibleNav(me: Me): NavItem[] {
  return NAV_ITEMS.filter((n) => !n.managerOnly || me.role === "manager");
}

// ログイン後の遷移先: 生鮮(order)の部門を持てば発注、惣菜(production)だけなら製造計画
export function homePath(me: Me): "/orders" | "/production" {
  const types = me.departments.map((d) => d.business_type);
  if (types.length > 0 && types.every((t) => t === "production")) {
    return "/production";
  }
  return "/orders";
}
