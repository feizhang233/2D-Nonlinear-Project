import type { ElementInput, JsonValue, ModelInput } from './domain'
import { nextPrefixedId } from './supports'

export type SectionShape =
  'custom' | 'rectangle' | 'circle' | 'i_section' | 'tube' | 'thickness'
export interface SectionDefinition {
  id: string
  name: string
  shape: SectionShape
  dimensions: Record<string, number>
}
export interface SectionLibrary {
  definitions: SectionDefinition[]
  default_id: string | null
}

function computeSectionProperties(
  section: SectionDefinition,
): { area: number; second_moment: number } | { thickness: number } {
  const d = section.dimensions
  const positive = (...keys: string[]) =>
    keys.forEach((key) => {
      if (!Number.isFinite(d[key]) || d[key] <= 0)
        throw new Error(
          `${key.replaceAll('_', ' ')} must be greater than zero.`,
        )
    })
  switch (section.shape) {
    case 'custom':
      positive('area', 'second_moment')
      return { area: d.area, second_moment: d.second_moment }
    case 'rectangle':
      positive('width', 'height')
      return {
        area: d.width * d.height,
        second_moment: (d.width * d.height ** 3) / 12,
      }
    case 'circle':
      positive('diameter')
      return {
        area: (Math.PI * d.diameter ** 2) / 4,
        second_moment: (Math.PI * d.diameter ** 4) / 64,
      }
    case 'tube': {
      positive('outer_diameter', 'wall_thickness')
      if (2 * d.wall_thickness >= d.outer_diameter)
        throw new Error(
          'Wall thickness must be less than half the outer diameter.',
        )
      const inner = d.outer_diameter - 2 * d.wall_thickness
      return {
        area: (Math.PI * (d.outer_diameter ** 2 - inner ** 2)) / 4,
        second_moment: (Math.PI * (d.outer_diameter ** 4 - inner ** 4)) / 64,
      }
    }
    case 'i_section': {
      positive('width', 'height', 'web_thickness', 'flange_thickness')
      if (2 * d.flange_thickness >= d.height || d.web_thickness >= d.width)
        throw new Error('Flanges and web must fit inside the overall section.')
      const h = d.height - 2 * d.flange_thickness
      return {
        area: 2 * d.width * d.flange_thickness + h * d.web_thickness,
        second_moment:
          (d.width * d.height ** 3 - (d.width - d.web_thickness) * h ** 3) / 12,
      }
    }
    case 'thickness':
      positive('thickness')
      return { thickness: d.thickness }
  }
}

export function defaultDimensions(shape: SectionShape): Record<string, number> {
  switch (shape) {
    case 'custom':
      return { area: 0.006, second_moment: 0.000085 }
    case 'rectangle':
      return { width: 0.2, height: 0.3 }
    case 'circle':
      return { diameter: 0.2 }
    case 'tube':
      return { outer_diameter: 0.2, wall_thickness: 0.01 }
    case 'i_section':
      return {
        width: 0.2,
        height: 0.3,
        web_thickness: 0.01,
        flange_thickness: 0.015,
      }
    case 'thickness':
      return { thickness: 0.1 }
  }
}

// Legacy models expose their existing property groups without changing the model/hash on read.
export function sectionLibrary(model: ModelInput): SectionLibrary {
  const stored = model.extensions?.section_library as unknown as
    SectionLibrary | undefined
  if (stored && Array.isArray(stored.definitions))
    return structuredClone(stored)
  const definitions: SectionDefinition[] = []
  model.elements.forEach((element) => {
    const shape = model.model_family === 'frame' ? 'custom' : 'thickness'
    const dimensions: Record<string, number> =
      shape === 'custom'
        ? {
            area: Number(element.properties.area),
            second_moment: Number(element.properties.second_moment),
          }
        : { thickness: Number(element.properties.thickness ?? 1) }
    if (
      !definitions.some(
        (item) =>
          JSON.stringify(item.dimensions) === JSON.stringify(dimensions),
      )
    ) {
      definitions.push({
        id: `S${definitions.length + 1}`,
        name: `Section ${definitions.length + 1}`,
        shape,
        dimensions,
      })
    }
  })
  return { definitions, default_id: definitions[0]?.id ?? null }
}

export function sectionIdForElement(
  model: ModelInput,
  element: ElementInput,
): string | undefined {
  if (model.extensions?.section_library)
    return typeof element.extensions?.section_id === 'string'
      ? element.extensions.section_id
      : undefined
  return sectionLibrary(model).definitions.find((section) =>
    Object.entries(sectionProperties(section)).every(
      ([key, value]) =>
        Number(element.properties[key] ?? (key === 'thickness' ? 1 : NaN)) ===
        value,
    ),
  )?.id
}

function initialized(model: ModelInput): ModelInput {
  const next = structuredClone(model)
  const library = sectionLibrary(model)
  if (!model.extensions?.section_library) {
    next.elements.forEach((element) => {
      element.extensions = {
        ...element.extensions,
        section_id: sectionIdForElement(model, element) ?? null,
      }
    })
  }
  next.extensions = {
    ...next.extensions,
    section_library: library as unknown as JsonValue,
  }
  return next
}

function withLibrary(model: ModelInput, library: SectionLibrary): ModelInput {
  return {
    ...model,
    extensions: {
      ...model.extensions,
      section_library: library as unknown as JsonValue,
    },
  }
}

export function addSection(model: ModelInput): {
  model: ModelInput
  id: string
} {
  const next = initialized(model)
  const library = sectionLibrary(next)
  const id = nextPrefixedId(
    'S',
    library.definitions.map((s) => s.id),
  )
  const shape = model.model_family === 'frame' ? 'custom' : 'thickness'
  library.definitions.push({
    id,
    name: `Section ${id.slice(1)}`,
    shape,
    dimensions: defaultDimensions(shape),
  })
  library.default_id ??= id
  return { model: withLibrary(next, library), id }
}

export function updateSection(
  model: ModelInput,
  section: SectionDefinition,
): ModelInput {
  let properties: Record<string, number> | null = null
  try {
    properties = sectionProperties(section)
  } catch {
    /* Invalid fields remain a visible draft; Apply is blocked. */
  }
  const next = initialized(model)
  const library = sectionLibrary(next)
  library.definitions = library.definitions.map((item) =>
    item.id === section.id ? structuredClone(section) : item,
  )
  next.elements.forEach((element) => {
    if (properties && element.extensions?.section_id === section.id)
      Object.assign(element.properties, properties)
  })
  return withLibrary(next, library)
}

export function assignSection(
  model: ModelInput,
  sectionId: string,
  elementIds: string[],
): ModelInput {
  const next = initialized(model)
  const section = sectionLibrary(next).definitions.find(
    (item) => item.id === sectionId,
  )
  if (!section) throw new Error('Select an existing section.')
  const properties = sectionProperties(section)
  next.elements.forEach((element) => {
    if (elementIds.includes(element.id)) {
      element.properties = { ...element.properties, ...properties }
      element.extensions = { ...element.extensions, section_id: sectionId }
    }
  })
  return next
}

export function setDefaultSection(model: ModelInput, id: string): ModelInput {
  const next = initialized(model)
  return withLibrary(next, { ...sectionLibrary(next), default_id: id })
}

export function deleteSection(model: ModelInput, id: string): ModelInput {
  if (
    model.elements.some((element) => sectionIdForElement(model, element) === id)
  )
    throw new Error(
      'Assign the elements to another section before deleting this section.',
    )
  const next = initialized(model)
  const library = sectionLibrary(next)
  library.definitions = library.definitions.filter((item) => item.id !== id)
  if (library.default_id === id)
    library.default_id = library.definitions[0]?.id ?? null
  return withLibrary(next, library)
}

export function applyDefaultSection(
  model: ModelInput,
  elementId: string,
): ModelInput {
  const id = sectionLibrary(model).default_id
  return id ? assignSection(model, id, [elementId]) : model
}

export function sectionError(model: ModelInput): string | null {
  try {
    for (const section of sectionLibrary(model).definitions) {
      if (!section.name.trim()) throw new Error('Enter a section name.')
      sectionProperties(section)
    }
    return null
  } catch (error) {
    return error instanceof Error ? error.message : 'Check section dimensions.'
  }
}

export function sectionProperties(
  section: SectionDefinition,
): Record<string, number> {
  const properties = computeSectionProperties(section)
  if (
    Object.values(properties).some(
      (value) => !Number.isFinite(value) || value <= 0,
    )
  )
    throw new Error('Section properties must be positive and finite.')
  return properties
}
