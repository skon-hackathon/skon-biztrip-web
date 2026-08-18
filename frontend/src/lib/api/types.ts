export type UserRole = 'EMPLOYEE' | 'MANAGER' | 'ADMIN';

export interface User {
	id: number;
	email: string;
	name: string;
	employee_no: string;
	position_code: string;
	role: UserRole;
	department_id: number;
	department_name: string;
	manager_id: number | null;
}

export interface LoginResponse {
	access_token: string;
	token_type: string;
	user: User;
}

export type TripStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'COMPLETED' | 'SETTLED';

export type ActivityAction =
	| 'CREATED'
	| 'UPDATED'
	| 'SUBMITTED'
	| 'APPROVED'
	| 'REJECTED'
	| 'COMPLETED'
	| 'SETTLED';

export interface Page<T> {
	items: T[];
	total: number;
	page: number;
	size: number;
}

export interface TripListItem {
	id: number;
	trip_no: string;
	title: string;
	city: string;
	country_code: string;
	destination_type_code: string;
	purpose_code: string;
	start_date: string;
	end_date: string;
	status: TripStatus;
	estimated_cost: string;
	user_id: number;
	user_name: string;
	approver_id: number | null;
	approver_name: string | null;
}

export interface TripDetail extends TripListItem {
	purpose_detail: string;
	transport_code: string;
	accommodation_code: string;
	cost_center_code: string;
	cost_center_name: string | null;
	submitted_at: string | null;
	approved_at: string | null;
	reject_reason: string | null;
	created_at: string;
	updated_at: string;
}

export interface TimelineEntry {
	id: number;
	action: ActivityAction;
	from_status: string | null;
	to_status: string | null;
	memo: string | null;
	actor_id: number;
	actor_name: string;
	created_at: string;
}

/** 신청·수정 폼이 다루는 필드. 수정은 이 타입의 부분집합을 보낸다. */
export interface TripInput {
	title: string;
	purpose_code: string;
	purpose_detail: string;
	destination_type_code: string;
	country_code: string;
	city: string;
	start_date: string;
	end_date: string;
	transport_code: string;
	accommodation_code: string;
	cost_center_code: string;
	estimated_cost: string;
}

export interface CodeItem {
	code: string;
	name: string;
	sort_order: number;
	extra: Record<string, unknown>;
}

export interface CodeGroup {
	group_code: string;
	name: string;
	description: string | null;
	codes: CodeItem[];
}

export interface Center {
	code: string;
	name: string;
	department_id: number | null;
}

export type NotificationType =
	| 'TRIP_SUBMITTED'
	| 'TRIP_APPROVED'
	| 'TRIP_REJECTED'
	| 'EXPENSE_SUBMITTED'
	| 'EXPENSE_APPROVED'
	| 'EXPENSE_REJECTED';

export interface NotificationItem {
	id: number;
	type: NotificationType;
	title: string;
	body: string;
	link_url: string | null;
	is_read: boolean;
	created_at: string;
}

export interface NotificationPage extends Page<NotificationItem> {
	unread: number;
}

export type ExpenseStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED';

export interface CardItem {
	id: number;
	card_no_masked: string;
	brand: string;
	is_active: boolean;
}

export interface CardTransactionItem {
	id: number;
	card_id: number;
	approved_at: string;
	merchant_name: string;
	merchant_category_code: string;
	amount: string;
	currency_code: string;
	amount_krw: string;
	is_cancelled: boolean;
}

export interface ExpenseItem {
	id: number;
	card_transaction_id: number | null;
	expense_category_code: string;
	amount_krw: string;
	memo: string | null;
	is_excluded: boolean;
	/** null이면 리포트 값 상속 */
	fund_center_code: string | null;
	cost_center_code: string | null;
	effective_fund_center_code: string | null;
	effective_cost_center_code: string | null;
	merchant_name: string | null;
	approved_at: string | null;
}

export interface ExpenseReportListItem {
	id: number;
	report_no: string;
	status: ExpenseStatus;
	trip_id: number;
	trip_no: string;
	trip_title: string;
	trip_start_date: string;
	trip_end_date: string;
	user_id: number;
	user_name: string;
	approver_id: number | null;
	approver_name: string | null;
	fund_center_code: string | null;
	cost_center_code: string | null;
	total_amount_krw: string;
	submitted_at: string | null;
	approved_at: string | null;
}

export interface ExpenseReportDetail extends ExpenseReportListItem {
	reject_reason: string | null;
	created_at: string;
	updated_at: string;
	items: ExpenseItem[];
}

export interface MatchCandidate {
	transaction_id: number;
	approved_at: string;
	merchant_name: string;
	merchant_category_code: string;
	amount_krw: string;
	suggested_category_code: string;
	reasons: string[];
	already_added: boolean;
}

export interface ExpenseItemInput {
	card_transaction_id?: number | null;
	expense_category_code: string;
	amount_krw?: string;
	memo?: string | null;
	fund_center_code?: string | null;
	cost_center_code?: string | null;
}

export interface ExpenseItemPatch {
	expense_category_code?: string;
	amount_krw?: string;
	memo?: string | null;
	is_excluded?: boolean;
	fund_center_code?: string | null;
	cost_center_code?: string | null;
}
