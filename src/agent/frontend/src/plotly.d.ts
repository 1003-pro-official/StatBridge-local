declare module "plotly.js-dist-min" {
  const Plotly: {
    react: (element: HTMLElement, data: unknown[], layout: object, config?: object) => Promise<unknown>;
    purge: (element: HTMLElement) => void;
    downloadImage: (element: HTMLElement, options: { format: string; filename: string; width: number; height: number }) => Promise<unknown>;
  };
  export default Plotly;
}
