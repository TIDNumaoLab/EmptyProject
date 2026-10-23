// まだ作っていない画面の仮置き(段階2以降で置き換える)
interface Props {
  title: string;
}

export default function PlaceholderPage({ title }: Props) {
  return (
    <section>
      <h1>{title}</h1>
      <p>この画面は準備中です。</p>
    </section>
  );
}
