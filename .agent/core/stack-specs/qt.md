# Qt/C++/QML Development Standards

> For Qt 6.x projects.

- **Scope**: All Qt/C++/QML files in the project (see [core-rules §3.3](../core-rules.md)).

---

## 1. Project Structure

```
project/
├── src/
│   ├── main.cpp
│   ├── models/
│   ├── views/
│   └── controllers/
├── qml/
│   ├── main.qml
│   └── components/
├── resources/
├── tests/
├── .agent/
└── CMakeLists.txt
```

---

## 2. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Class | PascalCase | `UserManager` |
| Method | camelCase | `getUserById` |
| Member variable | m_ + camelCase | `m_userName` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| QML file | PascalCase | `UserCard.qml` |
| Property | camelCase | `userName` |

---

## 3. C++ Class Template

```cpp
#ifndef USERMANAGER_H
#define USERMANAGER_H

#include <QObject>

class UserManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString userName READ userName WRITE setUserName NOTIFY userNameChanged)

public:
    explicit UserManager(QObject *parent = nullptr);

    QString userName() const;
    void setUserName(const QString &name);

signals:
    void userNameChanged();

private:
    QString m_userName;
};

#endif // USERMANAGER_H
```

---

## 4. QML Component Template

```qml
import QtQuick
import QtQuick.Controls

Item {
    id: root
    
    // Properties
    property string title: ""
    property bool isActive: false
    
    // Signals
    signal clicked()
    
    // Children
    Rectangle {
        anchors.fill: parent
        color: root.isActive ? "blue" : "gray"
        
        Text {
            anchors.centerIn: parent
            text: root.title
        }
        
        MouseArea {
            anchors.fill: parent
            onClicked: root.clicked()
        }
    }
}
```

---

## 5. Memory Management

```cpp
// Good: Use smart pointers
std::unique_ptr<Widget> widget = std::make_unique<Widget>();

// Good: Qt parent-child ownership
auto *button = new QPushButton(parentWidget);  // Parent owns button

// Avoid: Avoid raw new without parent
auto *widget = new QWidget();  // Memory leak risk
```

---

## 6. Signal/Slot Connections

```cpp
// Good: New syntax (compile-time checked)
connect(button, &QPushButton::clicked,
        this, &MyClass::handleClick);

// Good: Lambda
connect(button, &QPushButton::clicked, this, [this]() {
    handleClick();
});
```

---

## 7. Animation Guidelines

```qml
// Good: Smooth transitions (250-300ms)
Behavior on opacity {
    NumberAnimation { duration: 250 }
}

// Good: State-based animations
states: [
    State {
        name: "expanded"
        PropertyChanges { target: root; height: 200 }
    }
]

transitions: Transition {
    NumberAnimation { property: "height"; duration: 300 }
}
```

---

## 8. Build Commands

```bash
# Configure
cmake -B build -S .

# Build
cmake --build build

# Run
./build/app

# Test
ctest --test-dir build
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
