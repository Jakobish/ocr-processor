import Workspace from './components/Workspace';
export default function Page(){return <Workspace loginUrl={process.env.OCR_LOGIN_URL} membersUrl={process.env.OCR_MEMBERS_URL}/>;}
