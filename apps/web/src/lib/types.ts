export type Role = 'admin' | 'reviewer' | 'walker';
export type Shot = 'side' | 'head' | 'unknown';

export interface Team {
	id: string;
	name: string;
	city: string;
	role: Role;
}

export interface Me {
	id: string;
	display_name: string;
	teams: Team[];
}

export interface LineString {
	type: 'LineString';
	coordinates: [number, number][];
}

export interface Route {
	id: string;
	team_id: string;
	name: string;
	corridor_m: number;
	length_m: number;
	geometry: LineString;
}

export interface Pass {
	id: string;
	survey_id: string;
	pass_no: number;
	observer_id: string;
	observer_name: string;
	started_at: string;
	ended_at: string | null;
	locked: boolean;
	flags: string[];
	photo_count: number;
}

export interface Survey {
	id: string;
	team_id: string;
	name: string;
	status: 'open' | 'closed';
	start_window_local: string;
	timezone: string;
	route: Route;
	passes: Pass[];
}

export interface Member {
	user_id: string;
	display_name: string;
	role: Role;
}

export interface MemberInvite extends Member {
	invite_url: string;
}

export interface PhotoOut {
	id: string;
	pass_id: string;
	sha256: string;
	duplicate: boolean;
	flags: string[];
}
