// 本体APIの型定義

export type Role = "staff" | "manager";

export interface DepartmentRef {
  code: string;
  name: string;
  business_type: "order" | "production";
}

export interface Me {
  user_id: number;
  name: string;
  role: Role;
  // 所属部門
  departments: DepartmentRef[];
  // 操作できる部門(店長は全部門、担当者は所属部門)
  accessible_departments: DepartmentRef[];
}

export type ImportKind = "products" | "pos" | "inventory" | "waste";

export interface ImportLog {
  id: number;
  kind: ImportKind;
  department_code: string | null;
  file_name: string;
  imported_count: number;
  skipped_count: number;
  errors: { row: number; reason: string }[];
  imported_by_name: string | null;
  finished_at: string;
}

export interface InventoryLatest {
  product_code: string;
  product_name: string;
  quantity: number | null;
  based_at: string | null;
}

export interface InventoryInput {
  department_code: string;
  based_at: string;
  items: { product_code: string; quantity: number }[];
}

export interface Product {
  product_code: string;
  name: string;
  department_code: string;
  order_unit: number;
  lead_time_days: number;
  can_carry_over: boolean;
  cost_price: number | null;
  selling_price: number | null;
  is_active: boolean;
}

export interface Promotion {
  id: number;
  product_code: string;
  product_name: string;
  department_code: string;
  start_date: string;
  end_date: string;
  description: string;
  created_by_name: string | null;
}

export interface PromotionInput {
  product_code: string;
  start_date: string;
  end_date: string;
  description: string;
}

export interface CalendarDay {
  id: number;
  date: string;
  kind: "holiday" | "event";
  name: string;
}
