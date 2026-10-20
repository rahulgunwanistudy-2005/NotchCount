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

export interface CropOut {
	detection_id: string;
	url: string;
	pass_no: number;
	taken_at: string;
	view: Shot;
	quality: number;
}

export interface PairItem {
	kind: 'pair';
	pair_id: string;
	a: CropOut;
	b: CropOut;
	p_same: number | null;
	calibrated: boolean;
	route_m: number | null;
	minutes_apart: number;
	remaining: number;
}

export interface EarItem {
	kind: 'ear';
	detection_id: string;
	crop: CropOut;
	p_notched: number | null;
	p_not_visible: number | null;
	remaining: number;
}

export interface Progress {
	photos: Record<string, number>;
	detections: number;
	usable_detections: number;
	pairs: number;
	pairs_labelled: number;
	positive_labels: number;
	ears_labelled: number;
	review_pairs_left: number;
	review_ears_left: number;
	match_model: string | null;
	notch_model: string | null;
}

export interface Summary {
	median: number;
	low: number;
	high: number;
}

export interface ShareJson {
	notched: number;
	with_visible_ear: number;
	excluded_not_visible: number;
	share: number | null;
	low: number | null;
	high: number | null;
}

export interface EstimateResults {
	passes: { pass_no: number; started_at: string; ended_at: string | null; flags: string[] }[];
	sightings: number;
	pairs: number;
	decided_pairs: number;
	match_model: string[];
	comparability_problems: string[];
	git: string;
	counts?: { n1: number; n2: number; m2: number; distinct: number };
	chapman?: { status: string; n_hat: number | null; se: number | null; low: number | null; high: number | null };
	population?: Summary | null;
	share?: Summary | null;
	deficit?: Summary | null;
	point_share?: ShareJson;
	replicates?: number;
	no_recapture_fraction?: number;
	target_share?: number;
	single_pass?: { pass_no: number; individuals: number; share: ShareJson };
	review_flagged_clusters?: number;
}

export interface Estimate {
	id: string;
	survey_id: string;
	method: string;
	status: 'queued' | 'running' | 'done' | 'failed';
	params: Record<string, unknown>;
	results: EstimateResults | null;
	error: string | null;
	data_hash: string | null;
	code_version: string;
	seed: number;
	created_at: string;
}
