import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'מסמך · סביבת OCR',description:'סביבת עבודה מאובטחת לעיבוד מסמכים'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="he" dir="rtl"><body>{children}</body></html>;}
