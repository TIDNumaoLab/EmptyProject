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
