/** Keeps vtk.js out of the initial workspace payload. It is only relevant once a field asset exists. */
export async function loadFieldViewer(): Promise<void> {
  await import('vtk.js');
}
