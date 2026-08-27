const category = {
  id: "pilates-studio-edit",
  slug: "studio-edit",
  name: "Studio edit",
  parent_id: null,
};

const tag = {
  id: "pilates-demo-essential",
  slug: "studio-essential",
  name: "Studio essential",
};

export const PILATES_DEMO_PRODUCTS = [
  ["grip-socks", "Studio Grip Socks", "Soft cotton grip socks for steady reformer sessions.", 18, "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=900&auto=format&fit=crop"],
  ["massage-ball", "Cork Massage Ball", "A compact recovery tool for feet, hips, and shoulders.", 14, "https://images.unsplash.com/photo-1599447292180-45fd84092ef4?w=900&auto=format&fit=crop"],
  ["studio-bottle", "Everyday Studio Bottle", "An insulated bottle for class, commutes, and weekends.", 28, "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=900&auto=format&fit=crop"],
  ["linen-tote", "Linen Carry Tote", "A relaxed tote with room for layers, water, and essentials.", 32, "https://images.unsplash.com/photo-1594223274512-ad4803739b7c?w=900&auto=format&fit=crop"],
  ["recovery-tea", "Recovery Tea Blend", "A caffeine-free botanical blend for a slower post-class ritual.", 16, "https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=900&auto=format&fit=crop"],
  ["movement-journal", "Movement Journal", "A simple notebook for class notes, goals, and small wins.", 20, "https://images.unsplash.com/photo-1544816155-12df9643f363?w=900&auto=format&fit=crop"],
].map(([slug, name, description, price, image], index) => ({
  id: `pilates-demo-${index + 1}`,
  slug,
  name,
  description,
  price,
  currency: "USD",
  brand: "Form & Flow",
  category_id: category.id,
  images: [image],
  in_stock: true,
}));

export const isPilatesDemoSite = (site) =>
  String(site?.brand || "").trim().toLowerCase() === "form & flow";

export const getPilatesDemoCatalog = (filters = {}) => {
  const search = String(filters.search || "").trim().toLowerCase();
  let products = PILATES_DEMO_PRODUCTS.filter((product) =>
    !search || `${product.name} ${product.description}`.toLowerCase().includes(search)
  );

  if (filters.category && filters.category !== category.slug) products = [];
  if (filters.tag && filters.tag !== tag.slug) products = [];

  products = [...products].sort((left, right) => {
    if (filters.sort === "price_low") return left.price - right.price;
    if (filters.sort === "price_high") return right.price - left.price;
    if (filters.sort === "name") return left.name.localeCompare(right.name);
    return left.id.localeCompare(right.id);
  });

  return {
    categories: [category],
    tags: [tag],
    products,
    pagination: { page: 1, pages: 1, total: products.length, limit: 12 },
  };
};

export const getPilatesDemoProduct = (slug) => {
  const product = PILATES_DEMO_PRODUCTS.find((item) => item.slug === slug);
  if (!product) return null;
  return { product, category, tags: [tag] };
};
