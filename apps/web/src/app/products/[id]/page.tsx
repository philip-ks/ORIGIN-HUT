import {
  ProductWorkbench
} from "@/components/product-workbench";


export default async function ProductPage({
  params
}: {
  params: Promise<{
    id: string;
  }>;
}) {

  const {
    id
  } =
    await params;


  return (
    <ProductWorkbench
      productId={id}
    />
  );

}
