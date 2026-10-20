import type { MessageKey } from './en';

/**
 * Hindi drafts. NOT YET CHECKED by a Hindi-speaking team member (DESIGN_BRIEF rule), so the
 * Hindi switch stays hidden until REVIEWED is set to true by that reviewer.
 */
export const REVIEWED = false;

export const hi: Partial<Record<MessageKey, string>> = {
	'app.name': 'NotchCount',
	'nav.home': 'होम',
	'nav.protocol': 'फ़ील्ड कार्ड',
	'nav.signout': 'साइन आउट',
	'lang.switch': 'English',
	'capture.passOf': 'पास {n}',
	'capture.queued': '{n} अपलोड बाकी',
	'capture.allUploaded': 'सब अपलोड हो गए',
	'capture.offline': 'ऑफ़लाइन',
	'capture.gps': 'GPS ±{m} मी',
	'capture.gpsWaiting': 'GPS ढूँढ रहे हैं',
	'capture.sideShot': 'बगल से फ़ोटो',
	'capture.headShot': 'सिर की फ़ोटो',
	'capture.stepSide': 'पूरा कुत्ता, बगल से',
	'capture.stepHead': 'सिर, दोनों कान दिखें',
	'capture.dogs': 'इस पास में {n} कुत्ते',
	'capture.dogsOne': 'इस पास में 1 कुत्ता',
	'capture.shutter': 'फ़ोटो लें',
	'capture.skipHead': 'सिर की फ़ोटो छोड़ें',
	'capture.undo': 'वापस लें',
	'capture.endPass': 'पास खत्म करें'
};
