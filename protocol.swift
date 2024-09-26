import Foundation

class Shoe:CustomStringConvertible{
    var description: String {
        let doesOrDoesNotHaveLaces: String = hasLaces ? "with":"without"
       return  "\(color)ed shoe of size \(size) \(doesOrDoesNotHaveLaces) laces"
    }
    var color:String
    var size:Int
    var hasLaces:Bool

    init(color:String,size:Int,hasLaces:Bool){
        self.color = color
        self.size = size
        self.hasLaces = hasLaces
    }
}

var myShoe:Shoe = Shoe(color: "black", size: 7, hasLaces: true)
print(myShoe)
var myShoe2:Shoe = Shoe(color: "white", size: 6, hasLaces: false)
print(myShoe2)

struct Employee:Equatable{
    var firstName:String
    var lastName:String
    var job:String
    var dept:String
}

var emp1: Employee = Employee(firstName: "sam", lastName: "malone", job: "SE", dept: "java")

var emp2:Employee = Employee(firstName: "amritesh", lastName: "Kumar", job: "SE", dept: "Java")

print(emp1 == emp2)