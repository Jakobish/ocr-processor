import {NextRequest,NextResponse} from 'next/server';
import {identity} from '../../../lib/identity';
import {isSameOrigin} from '../../../lib/security';
export const dynamic='force-dynamic';
export async function GET(){try{return NextResponse.json((await identity()).profile,{headers:{'Cache-Control':'no-store'}});}catch(e){const kind=e instanceof Error?e.message:'';return NextResponse.json({error:kind==='integration_required'?kind:'unauthenticated'},{status:kind==='integration_required'?503:401});}}
export async function POST(req:NextRequest){
 if(!isSameOrigin(req.headers.get('origin'),process.env.OCR_PUBLIC_ORIGIN))return new Response(null,{status:403});
 try{const {tenant_id}=await req.json();if(typeof tenant_id!=='string')return new Response(null,{status:400});const {profile}=await identity(tenant_id);if(profile.tenant_id!==tenant_id)return new Response(null,{status:403});const response=NextResponse.json(profile);response.cookies.set('ocr_team',tenant_id,{httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'lax',path:'/'});response.headers.set('Cache-Control','no-store');return response;}catch{return new Response(null,{status:401});}
}
