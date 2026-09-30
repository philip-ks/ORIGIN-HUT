import type {
  Metadata
} from "next";

import type {
  ReactNode
} from "react";

import "./globals.css";


export const metadata: Metadata = {

  title:
    "Origin Hut — Product Trade Master",

  description:
    "Origin Hut export/import intelligence and trade operating platform"

};


export default function RootLayout({
  children
}: {
  children: ReactNode;
}) {

  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );

}
