from pydantic import BaseModel, ConfigDict, Field


class GroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    course: int = Field(default=1, ge=1, le=6)
    faculty: str | None = None
    students_count: int = Field(default=0, ge=0)


class GroupCreate(GroupBase):
    pass


class GroupRead(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TeacherBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    department: str | None = None


class TeacherCreate(TeacherBase):
    pass


class TeacherRead(TeacherBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DisciplineBase(BaseModel):
    name: str = Field(min_length=1, max_length=300)


class DisciplineCreate(DisciplineBase):
    pass


class DisciplineRead(DisciplineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ClassroomBase(BaseModel):
    number: str = Field(min_length=1, max_length=50)
    capacity: int | None = Field(default=None, ge=1)
    camera_url: str | None = None


class ClassroomCreate(ClassroomBase):
    pass


class ClassroomRead(ClassroomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
