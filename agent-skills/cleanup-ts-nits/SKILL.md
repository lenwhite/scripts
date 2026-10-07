---
name: cleanup-ts-nits
description: Clean up common TypeScript/React code patterns on staged files
argument-hint: "[files/patterns]"
---
Cleanup of some code patterns on staged files.

## Remove unnecessary type declarations and destructurings

Instead of:

```
export interface UseSearchProfilesOptions {
  urlState: SearchUrlState;
  setUrlState: (
    state: Partial<Omit<SearchUrlState, 'doc'>>,
  ) => void | Promise<URLSearchParams>;
}

export interface UseSearchProfilesResult {
  profiles: SearchProfileRecord[];
  selectedProfile: SearchProfileRecord | null;
  hasUnsavedChanges: boolean;
  isLoading: boolean;
  isMutating: boolean;

  selectProfile: (profileId: string) => void;
  createProfile: (name: string) => Promise<SearchProfileRecord>;
  updateProfile: () => Promise<void>;
  deleteProfile: () => Promise<void>;
  revertChanges: () => void;
}

export function useSearchProfiles(
  options: UseSearchProfilesOptions,
): UseSearchProfilesResult {
    const { urlState, setUrlState } = options;
    ...
}

```

Prefer:

export function useSearchProfiles(
  { urlState, setUrlState }: {
    urlState: SearchUrlState;
    setUrlState: (
      state: Partial<Omit<SearchUrlState, 'doc'>>,
    ) => void | Promise<URLSearchParams>;
  },
): {
  profiles: SearchProfileRecord[];
  selectedProfile: SearchProfileRecord | null;
  hasUnsavedChanges: boolean;
  isLoading: boolean;
  isMutating: boolean;

  selectProfile: (profileId: string) => void;
  createProfile: (name: string) => Promise<SearchProfileRecord>;
  updateProfile: () => Promise<void>;
  deleteProfile: () => Promise<void>;
  revertChanges: () => void;
}
```

This:
- Avoids exporting unecessary types which are not part of the module contract
- Reduces verbosity
- Makes it easier to refer to the types when declaring functions

## TS-Reset utils

```typescript
// Instead of:
const filteredArray = [1, 2, undefined].filter((item): item is number => {
  return !!item
}) // number[]

// we can do
const filteredArray = [1, 2, undefined].filter(Boolean)
```

## Type casting

Instead of casting api responses, prefer creating a zod schema whenever possible.

```typescript
// Instead of
const response = (await res.json()) as {
  data: Array<{
    id: string;
    data: Record<string, unknown>;
    _status?: string;
  }>;
};
const { data } = response;

// Create the equivalent zod schema
const KintoRecordSchema = z.object({
  id: z.string(),
  data: z.record(z.string(), z.unknown()),
  _status: z.string().optional(),
});

const KintoResponseSchema = z.object({
  data: z.array(KintoRecordSchema),
});
// ...
const response = KintoResponseSchema.parse(await res.json());
const { data } = response;
```

## Boolean React states
For boolean react states tracking open/close states - use the useDisclosure utility from Mantine.

```typescript
// Instead of
const [modelOpen, setModelOpen] = useState(true);

const handleOpen = () => setModelOpen(true);
<Component onOpen={handleOpen} ... />

// Do this
import { useDisclosure } from '@mantine/hooks';

const [modelOpen, model] = useDisclosure();
<Component onOpen={model.open} ... />
```

## Prefer inline memorization at usage to improve code locality

```tsx
// Instead of
const profileOptions = useMemo(
  () => profileState.profiles.map((p) => ({ id: p.id, name: p.data.name })),
  [profileState.profiles],
);
...
<Component options={profileOptions} />

// Prefer
<Component 
  options={useMemo(
    () => profileState.profiles.map((p) => ({ id: p.id, name: p.data.name })),
    [profileState.profiles],
  )}
/>
```
